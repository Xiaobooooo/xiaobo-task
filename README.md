Xiaobo Task [![X (formerly Twitter) Follow](https://img.shields.io/twitter/follow/0xiaobo888)](https://x.com/0xiaobo888)
===========
轻量级的同步/异步任务执行小框架，内置重试、日志、回调和数据源辅助工具，适合批量爬取、IO 操作或需要快速落地的小脚本。

![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?logo=python&tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2FXiaobooooo%2Fxiaobo-task%2Frefs%2Fheads%2Fmain%2Fpyproject.toml)
![Project Version from TOML](https://img.shields.io/badge/dynamic/toml?logo=semanticweb&color=orange&label=version&query=project.version&url=https%3A%2F%2Fraw.githubusercontent.com%2FXiaobooooo%2Fxiaobo-task%2Frefs%2Fheads%2Fmain%2Fpyproject.toml)

简介
----

- 同时提供同步 `XiaoboTask` 与异步 `AsyncXiaoboTask` 两种入口，接口保持一致。
- 基于 `tenacity` 的重试与延迟控制，支持全局配置或单次提交覆盖。
- 成功/失败/取消回调与统计汇总，日志默认标记任务编号和名称，便于追踪。
- 提供 txt 数据源读写和代理占位替换工具，批量任务可自动随机打乱顺序。
- 配置可来自 `.env`、环境变量或构造参数，适合以脚本或小服务形式运行。

安装
----
uv

```
uv add git+https://github.com/Xiaobooooo/xiaobo-task.git
```

pip

```
pip install git+https://github.com/Xiaobooooo/xiaobo-task.git
```

快速开始
--------
同步示例

```python
from xiaobo_task import XiaoboTask, Target


def task_func(target: Target):
    target.logger.info(f"工作中: {target.data}")
    return f"{target.data} done"


def on_success(target: Target, result):
    target.logger.info(f"回调 -> {result}")


if __name__ == "__main__":
    with XiaoboTask("DemoTask", max_workers=3, retries=1) as tm:
        tm.submit_tasks(
            task_func=task_func,
            source=["a", "b", "c"],
            on_success=on_success,
        )
        tm.wait()
        tm.statistics()
```

异步示例

```python
import asyncio
from xiaobo_task import AsyncXiaoboTask, Target


async def task_func(target: Target):
    await asyncio.sleep(1)
    return f"{target.data} ok"


async def main():
    async with AsyncXiaoboTask("AsyncDemo") as tm:
        tm.submit_tasks(
            task_func=task_func,
            source=["x", "y"],
        )
        await tm.wait()
        tm.statistics()


if __name__ == "__main__":
    asyncio.run(main())
```

从文件批量提交
--------------
`submit_tasks_from_file` 会按行读取 txt，默认分隔符为 `----`。示例文件见 `examples/example.txt`。

```python
async with AsyncXiaoboTask(retries=1) as tm:
    tm.submit_tasks_from_file(
        task_func=task_func,
        filename="example",  # 自动补全 .txt
    )
    await tm.wait()
```

配置与优先级
-----------
覆盖顺序：构造参数 > 环境变量/.env > 默认值。所有字段空字符串都会被视为未设置。

| 字段               | 默认    | 说明                            |
|------------------|-------|-------------------------------|
| `max_workers`    | 5     | 最大并发数（线程数或协程信号量）              |
| `shuffle`        | false | 提交前是否打乱任务顺序                   |
| `retries`        | 2     | 重试次数（`submit_task(s)` 参数可覆盖）  |
| `retry_delay`    | 0.0   | 重试间隔秒（0 为无延迟）                 |
| `proxy`          | -     | 代理地址，支持在字符串中用 `*****` 替换为数据预览 |
| `proxy_ipv6`     | -     | IPv6 代理                       |
| `proxy_api`      | -     | 代理API链接                       |
| `proxy_ipv6_api` | -     | IPv6 代理API链接                  |
| `use_proxy_ipv6` | false | 优先使用 IPv6 代理                  |
| `disable_proxy`  | false | 禁用代理分配                        |

回调与统计
---------

- 回调签名：成功 `(target, result)`，失败 `(target, error)`，取消 `(target)`；失败回调在重试耗尽后触发。
- `Target` 提供 `index`、`data`、`data_preview`、`proxy`、`logger` 等字段，默认日志格式包含任务名与编号。
- 调用 `statistics()` 输出成功/取消/失败计数及错误明细，可在同步/异步模式下直接调用。

代理与请求会话
-------------

- 代理模板示例：`user:pass@host:port` 或 `http://host:port`，包含 `*****` 时会用 `data_preview` 替换。
- 获取带代理的请求会话：`get_session()` 与 `get_async_session()`（基于 `curl-cffi`），方便在任务中直接复用。

示例与脚本
---------

- 同步示例：`python examples/example.py`
- 异步示例：`python examples/example_async.py`
- txt 数据示例：`examples/example.txt`

开发说明
-------

- 依赖 Python `>=3.13`；日志由 `loguru` 在包导入时初始化。
- 建议在提交前运行示例脚本，确认重试、代理和回调行为符合预期。
