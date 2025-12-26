# Xiaobo Task [![X (formerly Twitter) Follow](https://img.shields.io/twitter/follow/0xiaobo888)](https://x.com/0xiaobo888)

![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?logo=python&tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2FXiaobooooo%2Fxiaobo-task%2Frefs%2Fheads%2Fmain%2Fpyproject.toml)
![Project Version from TOML](https://img.shields.io/badge/dynamic/toml?logo=semanticweb&color=orange&label=version&query=project.version&url=https%3A%2F%2Fraw.githubusercontent.com%2FXiaobooooo%2Fxiaobo-task%2Frefs%2Fheads%2Fmain%2Fpyproject.toml)

## 简介

`xiaobo-task` 是一个通用的多线程 / 异步任务管理模块，面向需要批量执行任务、重试控制、回调处理与统计的场景。支持同步与异步两套接口，提供
`retry`、`callback`、代理池、任务统计等能力。

## 特性

- 同步 `XiaoboTask` 与异步 `AsyncXiaoboTask` 双接口
- 支持批量提交、失败重试、回调处理（on_success/on_error/on_cancel）
- 内置代理池（支持 IPv4 / IPv6 / API 拉取）
- 任务执行统计与错误汇总
- 配置自动从 `.env` / 环境变量加载（可在构造时覆盖）

## 安装

```bash
pip install xiaobo-task
```

> Python >= 3.10

## 快速开始（同步）

```python
import random
import time
from typing import Any

from loguru import logger
from xiaobo_task import XiaoboTask, Target, TaskFailed

APPNAME = "XiaoboTaskExample"


def example_task_processor(target: Target):
    target.logger.info(f"开始处理任务，数据: {target.data}")

    sleep_time = random.uniform(1, 3)
    time.sleep(sleep_time)

    # 抛出 TaskFailed 将不再重试
    if target.data == "data-6":
        raise TaskFailed("任务失败，不进行重试")

    return f"{target.data} 处理完毕，耗时 {sleep_time:.2f} 秒"


def on_task_success(target: Target, result: Any):
    target.logger.success(f"成功回调 -> {result}")


def on_task_error(target: Target, error: Exception):
    target.logger.error(f"失败回调 -> {error}")


def main():
    task_data_list = [f"data-{i}" for i in range(10)]
    with XiaoboTask(APPNAME, shuffle=False) as task_manager:
        task_manager.submit_tasks(
            task_func=example_task_processor,
            source=task_data_list,
            on_success=on_task_success,
            on_error=on_task_error,
            retries=1,
        )
        task_manager.wait()
        task_manager.statistics()


if __name__ == "__main__":
    main()
```

## 异步示例

```python
import asyncio
import random
from typing import Any

from loguru import logger
from xiaobo_task import Target, AsyncXiaoboTask, TaskFailed

APPNAME = "XiaoboTaskAsyncExample"


async def example_async_task_processor(target: Target):
    target.logger.info(f"开始处理任务，数据: {target.data}")
    await asyncio.sleep(random.uniform(1, 3))

    if target.data == "data-6":
        raise TaskFailed("任务失败，不进行重试")

    return f"{target.data} 处理完毕"


def on_task_success(target: Target, result: Any):
    target.logger.info(f"成功回调 -> {result}")


async def main():
    async with AsyncXiaoboTask(APPNAME, shuffle=False, retries=1) as task_manager:
        task_manager.submit_tasks(
            task_func=example_async_task_processor,
            source=[f"data-{i}" for i in range(10)],
            on_success=on_task_success,
        )
        await task_manager.wait()
        await task_manager.statistics()


if __name__ == "__main__":
    asyncio.run(main())
```

## 运行示例

```bash
python examples/example.py
python examples/example_async.py
```

异步示例会读取 `examples/example.txt` 作为任务源。

## 从文件批量读取任务

支持通过 `submit_tasks_from_file` 直接读取文本文件批量提交：

```python
task_manager.submit_tasks_from_file(
    task_func=example_task_processor,
    filename="example",  # 自动补全 .txt
)
```

## `.env` 配置项

配置默认从 `.env` / 环境变量加载，大小写不敏感，空字符串会自动回退到默认值。

**布尔值支持多种格式**：`true/false`、`1/0`、`on/off`、`yes/no`、`y/n`

**按任务名匹配**：`SHUFFLE`、`USE_PROXY_IPV6`、`DISABLE_PROXY` 支持 `task1&task2` 格式，仅对指定任务名生效。

可用配置项如下：

| 配置项              | 默认值     | 说明                                                                       |
|------------------|---------|--------------------------------------------------------------------------|
| `MAX_WORKERS`    | `5`     | 最大线程数                                                                    |
| `PROXY`          | *(空)*   | 代理，支持 `host:port` / `user:pass@host:port`，占位符 `*****` 自动替换为 index 或第一位数据 |
| `PROXY_IPV6`     | *(空)*   | IPv6 代理，格式同 `PROXY`                                                      |
| `PROXY_API`      | *(空)*   | 代理提取 API 地址（一行一个）                                                        |
| `PROXY_IPV6_API` | *(空)*   | IPv6 代理提取 API 地址                                                         |
| `RETRIES`        | `2`     | 重试次数（抛出 `TaskFailed` 不重试）                                                |
| `RETRY_DELAY`    | `0`     | 重试延迟（秒）                                                                  |
| `SHUFFLE`        | `false` | 是否打乱任务顺序，按照数量运行的任务，支持布尔值或任务名称，多个任务用&拼接，如： `task1&task2`                  |
| `USE_PROXY_IPV6` | `false` | 是否优先使用 IPv6 代理，支持布尔值或任务名称，多个任务用&拼接，如： `task1&task2`                      |
| `DISABLE_PROXY`  | `false` | 是否禁用代理，支持布尔值或任务名称，多个任务用&拼接，如：`task1&task2`                               |

示例 `.env`：

```dotenv
# 布尔值支持: true/false 1/0 on/off yes/no y/n
MAX_WORKERS=8
# 代理格式: host:port 或 user:pass@host:port，占位符 ***** 会自动替换
PROXY=abc.com:123
PROXY_IPV6=ipv6.abc.com:123
# 代理提取 API（一行一个）
PROXY_API=https://abc.com/proxies
PROXY_IPV6_API=https://abc.com/ipv6/proxies
RETRIES=2
RETRY_DELAY=0
# 布尔值 所有任务都打乱运行顺序
SHUFFLE=true
# 按任务名匹配示例: 仅 TaskA 使用IPV6代理
USE_PROXY_IPV6=task1
# 按任务名匹配示例: 仅 TaskA 和 TaskB 禁用代理
DISABLE_PROXY=TaskA&TaskB
```

> 也可以在初始化时通过关键字参数覆盖任意配置，例如 `XiaoboTask(max_workers=10, retries=3)`。

## data 目录说明

读取 `.txt` 文件时会自动补全后缀，并按以下顺序查找：

1) 脚本所在目录
    ```
    project_root/
      data/
        example.txt
    ```
2) 项目根目录同级的 `data/` 目录
    ```
    project_root/
      example.txt
      main.py
    ```

## 依赖

核心依赖包括：`curl-cffi`、`loguru`、`pydantic-settings`、`python-dotenv`、`tenacity`。

## 许可证

暂无开源协议（No License）。
