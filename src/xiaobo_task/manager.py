import asyncio
import inspect
from abc import abstractmethod, ABC
from asyncio import Task
from concurrent.futures import ThreadPoolExecutor, Future, CancelledError
from typing import Callable, Any, Optional, overload, Awaitable

from xiaobo_task.domain import Target


class _BaseTaskManager(ABC):
    def __init__(self, max_workers: Optional[int] = None):
        if max_workers is not None and max_workers <= 0:
            raise ValueError("max_workers 必须为正整数或 None。")

    @overload
    def submit_task(
            self,
            task_func: Callable[..., Any],
            target: Optional[Target] = None,
            on_success: Optional[Callable[[Target, Any], None]] = None,
            on_error: Optional[Callable[[Target, Exception], None]] = None,
            on_cancel: Optional[Callable[[Target], None]] = None,
    ) -> Future: ...

    @overload
    async def submit_task(
            self,
            task_func: Callable[..., Any],
            target: Optional[Target] = None,
            on_success: Optional[Callable[[Target, Any], Awaitable[Any]]] = None,
            on_error: Optional[Callable[[Target, Exception], Awaitable[Any]]] = None,
            on_cancel: Optional[Callable[[Target], Awaitable[Any]]] = None,
    ) -> Task: ...

    @abstractmethod
    def submit_task(
            self,
            task_func: Callable[..., Any],
            target: Optional[Target] = None,
            on_success: Optional[Callable[[Target, Any], None]] = None,
            on_error: Optional[Callable[[Target, Exception], None]] = None,
            on_cancel: Optional[Callable[[Target], None]] = None,
    ) -> Any:
        raise NotImplementedError


    @overload
    def shutdown(self, wait: bool = True, cancel_tasks: bool = False): ...

    @overload
    async def shutdown(self, wait: bool = True, cancel_tasks: bool = False): ...

    @abstractmethod
    def shutdown(self, wait: bool = True, cancel_tasks: bool = False):
        raise NotImplementedError

class TaskManager(_BaseTaskManager):
    """通用同步任务池管理器"""

    def __init__(self, max_workers: Optional[int] = None):
        super().__init__(max_workers)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit_task(
            self,
            task_func: Callable[..., Any],
            target: Optional[Target] = None,
            on_success: Optional[Callable[[Target, Any], None]] = None,
            on_error: Optional[Callable[[Target, Exception], None]] = None,
            on_cancel: Optional[Callable[[Target], None]] = None,
    ) -> Future:
        """提交一个新任务到任务池池执行。

        参数:
            task_func (Callable): 要在任务池中执行的、已被完全包装好的目标函数。
            target (Optional[Target]): 与任务关联的 Target 对象，主要用于回调。
            on_success (Optional[Callable]): 任务成功完成时调用的回调函数。
            on_error (Optional[Callable]): 任务执行过程中发生异常时调用的回调函数。
            on_cancel (Optional[Callable]): 任务被取消时调用的回调函数。
        """

        def _task_done_callback(_future: Future):
            try:
                result = _future.result()
                if on_success:
                    on_success(target, result)
            except CancelledError:
                if on_cancel:
                    on_cancel(target)
            except Exception as e:
                if on_error:
                    on_error(target, e)

        # 直接提交调用方传入的、不带参数的包装函数
        future = self.executor.submit(task_func)
        future.add_done_callback(lambda f: _task_done_callback(f))
        return future

    def shutdown(self, wait: bool = True, cancel_tasks: bool = False):
        """关闭任务池"""
        self.executor.shutdown(wait, cancel_futures=cancel_tasks)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(False, True)


class AsyncTaskManager(_BaseTaskManager):
    """通用异步任务池管理器"""

    def __init__(self, max_workers: Optional[int] = None):
        super().__init__(max_workers)
        self.sem = asyncio.Semaphore(max_workers) if max_workers else None
        self._tasks: set[Task] = set()

    def submit_task(
            self,
            task_func: Callable[..., Any],
            target: Optional[Target] = None,
            on_success: Optional[Callable[[Target, Any], None]] = None,
            on_error: Optional[Callable[[Target, Exception], None]] = None,
            on_cancel: Optional[Callable[[Target], None]] = None,
    ) -> Task:
        """提交一个新任务到任务池执行。

        参数:
            task_func (Callable): 要在任务池中执行的、已被完全包装好的目标函数。
            target (Optional[Target]): 与任务关联的 Target 对象，主要用于回调。
            on_success (Optional[Callable]): 任务成功完成时调用的回调函数。
            on_error (Optional[Callable]): 任务执行过程中发生异常时调用的回调函数。
            on_cancel (Optional[Callable]): 任务被取消时调用的回调函数。
        """

        async def _run_with_semaphore():
            current = asyncio.current_task()
            if self.sem:
                async with self.sem:
                    if current:
                        setattr(current, "started", True)
                    return await task_func()
            if current:
                setattr(current, "started", True)
            return await task_func()

        async def _run_callback(cb: Callable[..., Any], *args):
            result = cb(*args)
            if inspect.isawaitable(result):
                await result

        async def _task_done_callback(_future: Task):
            try:
                result = _future.result()
                if on_success:
                    await _run_callback(on_success, target, result)
            except asyncio.CancelledError:
                if on_cancel:
                    await _run_callback(on_cancel, target)
            except Exception as e:
                if on_error:
                    await _run_callback(on_error, target, e)

        task = asyncio.create_task(_run_with_semaphore())
        task.started = False  # 标记任务是否真正开始执行，用于优雅取消
        task.add_done_callback(lambda f: asyncio.create_task(_task_done_callback(f)))
        task.add_done_callback(lambda t: self._tasks.discard(t))
        self._tasks.add(task)
        return task

    async def shutdown(self, wait: bool = True, cancel_tasks: bool = False):
        """关闭任务池"""
        tasks = set(self._tasks)
        if cancel_tasks:
            for task in tasks:
                if not task.done():
                    task.cancel()

        if wait and tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._tasks.clear()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.shutdown(False, True)
