import asyncio
import inspect
import os
import random
import threading
import time
import traceback
from abc import ABC, abstractmethod
from asyncio import Task
from concurrent import futures
from concurrent.futures import Future
from typing import Optional, Callable, Any, List, Union, Type, Awaitable, overload

from loguru import logger
from tenacity import retry_if_not_exception_type, stop_after_attempt, wait_fixed, retry

from xiaobo_task import util
from xiaobo_task.domain import Target
from xiaobo_task.exceptions import TaskFailed
from xiaobo_task.manager import BaseTaskManager, TaskManager, AsyncTaskManager
from xiaobo_task.proxy_pool import ProxyPool
from xiaobo_task.settings import Settings


class BaseTask(ABC):

    def __init__(self, task_manager_cls: Type[BaseTaskManager], name: str = "XiaoboTask", **kwargs):
        """初始化 XiaoboTask 实例。

        配置会自动从 .env 文件、环境变量或默认值加载。
        也可以通过在构造函数中传递关键字参数来直接覆盖任何配置项。

        参数:
            name (str): 任务实例的名称。
            **kwargs: 任何配置参数，将覆盖 .env 文件或默认值。
                      例如: max_workers=10, retries=5
        """
        self.logger = logger.bind(name=name)

        # 过滤掉值为 None 的 kwargs，这样 pydantic 才会继续查找 env/default
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}

        # 使用 pydantic-settings 加载配置，并允许通过参数覆盖
        self.settings = Settings(task_name=name, **filtered_kwargs)

        # 初始化简化的 TaskManager
        self._manager = task_manager_cls(self.settings.max_workers)

        self._proxy_pool = ProxyPool(
            self.settings.proxy,
            self.settings.proxy_ipv6,
            self.settings.proxy_api,
            self.settings.proxy_ipv6_api,
            self.settings.use_proxy_ipv6,
            self.settings.disable_proxy
        )

        # 记录加载的配置信息
        self._log_settings()

        self._stats = {"success": 0, "pending": 0, "error": 0, "cancel": 0}
        self._errors: List[str] = []

    def _log_settings(self):
        """以中文格式，逐行记录加载的配置信息，并处理中文字符对齐。"""

        self.logger.info("--- 任务配置 ---")

        # 遍历 pydantic 模型的字段以获取描述和值
        for field_name, field_info in self.settings.model_fields.items():
            if not field_info.description:
                continue
            description = field_info.description
            value = getattr(self.settings, field_name)

            # 对特殊值进行友好显示
            if value is None:
                value_str = "未设置"
            elif isinstance(value, bool):
                value_str = "是" if value else "否"
            else:
                value_str = str(value)

            self.logger.info(f"{description}: {value_str}")

        self.logger.info("--- 任务配置 ---")

    def submit_tasks(
            self,
            task_func: Callable[..., Any],
            source: Union[int, List[Any]],
            on_success: Optional[Callable[[Target, Any], None]] = None,
            on_error: Optional[Callable[[Target, Exception], None]] = None,
            on_cancel: Optional[Callable[[Target], None]] = None,
            retries: Optional[int] = None,
            retry_delay: Optional[float] = None,
    ):
        """
        根据指定的源批量提交任务。

        源可以是整数（提交指定数量的任务）或列表（为每个元素提交一个任务）。

        参数:
            source (Union[int, List[Any]]): 任务源。
            task_func (Callable): 要执行的任务函数。
            ... (其他参数)
        """
        if isinstance(source, int):
            items = range(source)
        elif isinstance(source, list):
            items = source[:]
            if self.settings.shuffle:
                random.shuffle(items)
        else:
            raise TypeError("'source' 必须是 int 或 list 类型。")

        if not items:
            self.logger.warning("任务数量必须大于 0。")
            return

        self.logger.info(f"本次提交 {len(items)} 个任务")

        for index, item in enumerate(items):
            task_name = f"{index + 1:05d}"
            task_logger = self.logger.bind(name=task_name)

            data_preview = str(item[0]) if isinstance(item, (list, tuple)) else item

            target = Target(index=index, data=item, data_preview=data_preview, logger=task_logger)

            self.submit_task(
                task_func=task_func,
                target=target,
                on_success=on_success,
                on_error=on_error,
                on_cancel=on_cancel,
                retries=retries,
                retry_delay=retry_delay,
            )

    def submit_tasks_from_file(
            self,
            task_func: Callable[..., Any],
            filename: str,
            separator: str = '----',
            on_success: Optional[Callable[[Target, Any], None]] = None,
            on_error: Optional[Callable[[Target, Exception], None]] = None,
            on_cancel: Optional[Callable[[Target], None]] = None,
            retries: Optional[int] = None,
            retry_delay: Optional[float] = None,
    ):
        """
        从文件中读取数据并批量提交任务。
        ... (其他文档)
        """
        try:
            lines = util.read_txt_file_lines(filename)
            source_list = [line.split(separator) for line in lines]
        except (FileNotFoundError, IOError) as e:
            self.logger.error(f"文件 '{filename}' 解析失败: {e}")
            return

        self.submit_tasks(
            task_func=task_func,
            source=source_list,
            on_success=on_success,
            on_error=on_error,
            on_cancel=on_cancel,
            retries=retries,
            retry_delay=retry_delay,
        )

    @overload
    @abstractmethod
    def _increment_stat(self, key: str):
        """线程安全地自增指定回调计数。"""

    @overload
    @abstractmethod
    async def _increment_stat(self, key: str):
        """线程安全地自增指定回调计数。"""

    @overload
    @abstractmethod
    def _get_stat(self, key: str):
        """线程安全地获取单个回调计数。"""

    @overload
    @abstractmethod
    async def _get_stat(self, key: str):
        """线程安全地获取单个回调计数。"""

    @overload
    @abstractmethod
    def get_success_count(self) -> int:
        """获取成功任务数。"""

    @overload
    @abstractmethod
    async def get_success_count(self) -> int:
        """获取成功任务数。"""

    @overload
    @abstractmethod
    def get_error_count(self) -> int:
        """获取失败任务数。"""

    @overload
    @abstractmethod
    async def get_error_count(self) -> int:
        """获取失败任务数。"""

    @overload
    @abstractmethod
    def get_cancel_count(self) -> int:
        """获取取消任务数。"""

    @overload
    @abstractmethod
    async def get_cancel_count(self) -> int:
        """获取取消任务数。"""

    @overload
    @abstractmethod
    def statistics(self):
        """
        返回统计信息的字符串报告，包含成功/失败/取消个数，
        以及按顺序列出的错误详情（格式: data/data[0]: 错误信息）。
        """

    @overload
    @abstractmethod
    async def statistics(self):
        """
        返回统计信息的字符串报告，包含成功/失败/取消个数，
        以及按顺序列出的错误详情（格式: data/data[0]: 错误信息）。
        """

    @abstractmethod
    def submit_task(
            self,
            task_func: Callable[..., Any],
            target: Optional[Target] = None,
            on_success: Optional[Callable[[Target, Any], None]] = None,
            on_error: Optional[Callable[[Target, Exception], None]] = None,
            on_cancel: Optional[Callable[[Target], None]] = None,
            retries: Optional[int] = None,
            retry_delay: Optional[float] = None,
    ) -> Future | Task:
        """提交任务到任务池"""

    @overload
    @abstractmethod
    def wait(self):
        """等待已提交的任务完成，支持捕获 Ctrl+C 中断。"""

    @overload
    @abstractmethod
    async def wait(self):
        """等待已提交的任务完成，支持捕获 Ctrl+C 中断。"""

    @overload
    @abstractmethod
    def shutdown(self):
        """等待已提交的任务完成，支持捕获 Ctrl+C 中断。"""

    @overload
    @abstractmethod
    async def shutdown(self):
        """等待已提交的任务完成，支持捕获 Ctrl+C 中断。"""


class XiaoboTask(BaseTask):

    def __init__(self, name: str = "XiaoboTask", **kwargs):
        """初始化 XiaoboTask 实例。

        配置会自动从 .env 文件、环境变量或默认值加载。
        也可以通过在构造函数中传递关键字参数来直接覆盖任何配置项。

        参数:
            name (str): 任务实例的名称。
            **kwargs: 任何配置参数，将覆盖 .env 文件或默认值。
                      例如: max_workers=10, retries=5
        """
        super().__init__(TaskManager, name, **kwargs)
        self._stats_lock = threading.Lock()

    def _increment_stat(self, key: str):
        with self._stats_lock:
            self._stats[key] += 1

    def _get_stat(self, key: str):
        with self._stats_lock:
            return self._stats.get(key, 0)

    def get_success_count(self) -> int:
        return self._get_stat('success')

    def get_error_count(self) -> int:
        return self._get_stat('error')

    def get_cancel_count(self) -> int:
        return self._get_stat('cancel')

    def statistics(self):
        with self._stats_lock:
            self.logger.opt(colors=True).info(
                "成功: {}   取消: {}   失败: {}\n<red>{}</red>",
                self._stats["success"], self._stats["cancel"], self._stats["error"], '\n'.join(self._errors)
            )

    def submit_task(
            self,
            task_func: Callable[..., Any],
            target: Optional[Target] = None,
            on_success: Optional[Callable[[Target, Any], None]] = None,
            on_error: Optional[Callable[[Target, Exception], None]] = None,
            on_cancel: Optional[Callable[[Target], None]] = None,
            retries: Optional[int] = None,
            retry_delay: Optional[float] = None,
    ):
        """提交一个新任务。

        此方法现在负责包装任务函数，为其添加重试和异步处理逻辑，
        然后将包装好的函数提交给底层的 TaskManager。
        """

        def on_task_success(t: Target, result: Any):
            self._increment_stat("success")
            t.logger.success(f"✅ [{target.data_preview}]任务执行成功")
            if on_success:
                on_success(t, result)

        def on_task_cancel(t: Target):
            self._increment_stat("cancel")
            t.logger.warning(f"⏹️ [{target.data_preview}]任务取消")
            if on_cancel:
                on_cancel(t)

        def on_task_error(t: Target, error: Exception):
            if isinstance(error, futures.CancelledError):
                on_task_cancel(t)
                return
            self._increment_stat("error")

            error_text = f"{error.__class__.__name__}: {error}"
            try:
                tb = error.__traceback__
                last_frame = traceback.extract_tb(tb)[-1]
                filename = os.path.basename(last_frame.filename)
                lineno = last_frame.lineno
                error_text = f'[{filename}:{lineno}] {error_text}'
                t.logger.error(f"❌ [{target.data_preview}]任务执行失败 -> {error_text}")
            except Exception:
                t.logger.error(f"❌ [{target.data_preview}]任务执行失败 -> {error_text}")

            error_text = f"{target.data_preview}: {error_text}"
            with self._stats_lock:
                self._errors.append(error_text)

            if on_error:
                on_error(t, error)

        def _refresh_proxy(replacement: Optional[str] = None, use_proxy_ipv6: Optional[bool] = None):
            replacement_text = (replacement if replacement is not None else f'{target.data_preview}({time.time()})')
            proxy = self._proxy_pool.get_proxy(replacement=replacement_text, _use_proxy_ipv6=use_proxy_ipv6)
            target.proxy = proxy
            return proxy

        target.refresh_proxy = _refresh_proxy

        effective_retries = retries if retries is not None else self.settings.retries
        effective_retry_delay = retry_delay if retry_delay is not None else self.settings.retry_delay

        # --- 将所有执行逻辑包装到一个函数中 ---
        def _wrapped_task_executor():
            attempt_counter = {"n": 0}  # tenacity 不直接提供 attempt 编号，使用闭包计数

            def log_before_retry(retry_state):
                if target and target.logger:
                    exc = retry_state.outcome.exception()
                    target.logger.warning(
                        f"🔄 [{target.data_preview}]任务执行失败，将在 {retry_state.next_action.sleep:.2f} 秒后进行第 {retry_state.attempt_number} 次重试... "
                        f"异常: {repr(exc)}"
                    )

            @retry(
                retry=retry_if_not_exception_type(TaskFailed),
                stop=stop_after_attempt(effective_retries + 1),
                wait=wait_fixed(effective_retry_delay) if effective_retry_delay > 0 else None,
                before_sleep=log_before_retry,
                reraise=True
            )
            def task_to_run():
                attempt_counter["n"] += 1
                if target and target.logger:
                    target.logger.info(f"🚀 [{target.data_preview}]第 {attempt_counter['n']} 次运行")
                # 每次重试提供新的代理
                _refresh_proxy(replacement=f'{target.data_preview}({attempt_counter["n"]})')
                return task_func(target)

            return task_to_run()

        # --- 包装结束 ---
        self._manager.submit_task(
            task_func=_wrapped_task_executor,
            target=target,
            on_success=on_task_success,
            on_error=on_task_error,
            on_cancel=on_task_cancel,
        )

    def wait(self, wait_callbacks: bool = True):
        """等待已提交的任务完成，支持捕获 Ctrl+C 中断。"""
        try:
            self._manager.wait(wait_callbacks)
        except (KeyboardInterrupt, futures.CancelledError):
            self.logger.warning("用户中断，取消未开始的任务，等待运行中的任务...")
            try:
                self.shutdown(False, True)
                self._manager.wait(wait_callbacks)
            except (KeyboardInterrupt, futures.CancelledError):
                self.logger.error("用户强制中断，程序退出！")
                os._exit(0)

    def shutdown(self, wait: bool = True, cancel_tasks: bool = False, wait_callbacks: bool = True):
        self._manager.shutdown(wait, cancel_tasks, wait_callbacks)

    def __enter__(self):
        """实现上下文管理器协议，在 'with' 语句开始时返回自身。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """在 'with' 语句结束时，安全关闭底层的 TaskManager。"""
        self.shutdown(True, True)


class AsyncXiaoboTask(BaseTask):
    def __init__(self, name: str = "AsyncXiaoboTask", **kwargs):
        """初始化 AsyncXiaoboTask 实例。

        配置会自动从 .env 文件、环境变量或默认值加载。
        也可以通过在构造函数中传递关键字参数来直接覆盖任何配置项。

        参数:
            name (str): 任务实例的名称。
            **kwargs: 任何配置参数，将覆盖 .env 文件或默认值。
                      例如: max_workers=10, retries=5
        """
        super().__init__(AsyncTaskManager, name, **kwargs)
        self._stats_lock = asyncio.Lock()

    async def _increment_stat(self, key: str):
        async with self._stats_lock:
            self._stats[key] += 1

    async def _get_stat(self, key: str):
        async with self._stats_lock:
            return self._stats.get(key, 0)

    async def get_success_count(self) -> int:
        return await self._get_stat('success')

    async def get_error_count(self) -> int:
        return await self._get_stat('error')

    async def get_cancel_count(self) -> int:
        return await self._get_stat('cancel')

    async def statistics(self):
        async with self._stats_lock:
            self.logger.opt(colors=True).info(
                "成功: {}   取消: {}   失败: {}\n<red>{}</red>",
                self._stats["success"], self._stats["cancel"], self._stats["error"], '\n'.join(self._errors)
            )

    def submit_task(
            self,
            task_func: Callable[..., Any],
            target: Optional[Target] = None,
            on_success: Optional[Callable[[Target, Any], Awaitable | None]] = None,
            on_error: Optional[Callable[[Target, Exception], Awaitable | None]] = None,
            on_cancel: Optional[Callable[[Target], Awaitable | None]] = None,
            retries: Optional[int] = None,
            retry_delay: Optional[float] = None,
    ):
        """提交一个新任务。

        此方法现在负责包装任务函数，为其添加重试和异步处理逻辑，
        然后将包装好的函数提交给底层的 TaskManager。
        """

        async def _run_callback(cb: Callable[..., Any], *args):
            result = cb(*args)
            if inspect.isawaitable(result):
                await result

        async def on_task_success(t: Target, result: Any):
            await self._increment_stat("success")
            t.logger.success(f"✅ [{target.data_preview}]任务执行成功")
            if on_success:
                await _run_callback(on_success, t, result)

        async def on_task_cancel(t: Target):
            await self._increment_stat("cancel")
            t.logger.warning(f"⏹️ [{target.data_preview}]任务取消")
            if on_cancel:
                await _run_callback(on_cancel, t)

        async def on_task_error(t: Target, error: Exception):
            if isinstance(error, asyncio.CancelledError):
                await on_task_cancel(t)
                return
            await self._increment_stat("error")

            error_text = f"{error.__class__.__name__}: {error}"
            try:
                tb = error.__traceback__
                last_frame = traceback.extract_tb(tb)[-1]
                filename = os.path.basename(last_frame.filename)
                lineno = last_frame.lineno
                error_text = f'[{filename}:{lineno}] {error_text}'
                t.logger.error(f"❌ [{target.data_preview}]任务执行失败 -> {error_text}")
            except Exception:
                t.logger.error(f"❌ [{target.data_preview}]任务执行失败 -> {error_text}")

            error_text = f"{target.data_preview}: {error_text}"
            async with self._stats_lock:
                self._errors.append(error_text)

            if on_error:
                await _run_callback(on_error, t, error)

        def _refresh_proxy(replacement: Optional[str] = None, use_proxy_ipv6: Optional[bool] = None):
            replacement_text = (replacement if replacement is not None else f'{target.data_preview}({time.time()})')
            proxy = self._proxy_pool.get_proxy(replacement=replacement_text, _use_proxy_ipv6=use_proxy_ipv6)
            target.proxy = proxy
            return proxy

        target.refresh_proxy = _refresh_proxy

        effective_retries = retries if retries is not None else self.settings.retries
        effective_retry_delay = retry_delay if retry_delay is not None else self.settings.retry_delay

        # --- 将所有执行逻辑包装到一个函数中 ---
        async def _wrapped_task_executor():
            asyncio.current_task().started = True
            attempt_counter = {"n": 0}  # tenacity 不直接提供 attempt 编号，使用闭包计数

            def log_before_retry(retry_state):
                if target and target.logger:
                    exc = retry_state.outcome.exception()
                    target.logger.warning(
                        f"🔄 [{target.data_preview}]任务执行失败，将在 {retry_state.next_action.sleep:.2f} 秒后进行第 {retry_state.attempt_number} 次重试... "
                        f"异常: {repr(exc)}"
                    )

            @retry(
                retry=retry_if_not_exception_type(TaskFailed),
                stop=stop_after_attempt(effective_retries + 1),
                wait=wait_fixed(effective_retry_delay) if effective_retry_delay > 0 else None,
                before_sleep=log_before_retry,
                reraise=True
            )
            async def task_to_run():
                attempt_counter["n"] += 1
                if target and target.logger:
                    target.logger.info(f"🚀 [{target.data_preview}]第 {attempt_counter['n']} 次运行")
                # 每次重试提供新的代理
                _refresh_proxy(replacement=f'{target.data_preview}({attempt_counter["n"]})')
                return await task_func(target)

            return await task_to_run()

        # --- 包装结束 ---
        self._manager.submit_task(
            task_func=_wrapped_task_executor,
            target=target,
            on_success=on_task_success,
            on_error=on_task_error,
            on_cancel=on_task_cancel,
        )

    async def wait(self, wait_callbacks: bool = True):
        """等待已提交的任务完成，支持捕获 Ctrl+C 中断。"""
        try:
            await self._manager.wait(wait_callbacks)
        except (KeyboardInterrupt, asyncio.CancelledError):
            self.logger.warning("用户中断，取消未开始的任务，等待运行中的任务...")
            try:
                await self.shutdown(False, True)
                await self._manager.wait(wait_callbacks)
            except (KeyboardInterrupt, asyncio.CancelledError):
                self.logger.error("用户强制中断，程序退出！")
                os._exit(0)

    async def shutdown(self, wait: bool = True, cancel_tasks: bool = False, wait_callbacks: bool = True):
        await self._manager.shutdown(wait, cancel_tasks, wait_callbacks)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.shutdown(True, True)
