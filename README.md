Xiaobo Task
============

通用的同步/异步任务执行小框架，内置重试、日志和简洁的回调接口，适合快速批量执行网络或 IO 任务。

特性
----
- 同步 `XiaoboTask` 与异步 `AsyncXiaoboTask` 双实现
- 基于 `tenacity` 的重试与延迟控制，可在全局或单次提交时覆盖
- 任务级别回调（成功/失败/取消）以及汇总统计
- 支持代理（IPv4/IPv6）占位替换，批量任务可自动随机打乱
- 简单的 txt 数据源读写工具 `read_txt_file_lines` / `write_txt_file`
- 使用 `.env`/环境变量加载配置，可通过构造参数直接覆盖

安装
----
### uv
```
uv add git+https://github.com/Xiaobooooo/xiaobo_task.git
```
### pip
```
pip install git+https://github.com/Xiaobooooo/xiaobo_task.git
```

快速上手（同步）
----------------
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

快速上手（异步）
---------------
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
`submit_tasks_from_file` 会按行读取 txt，默认分隔符 `----`。示例文件见 `examples/example.txt`。
```python
async with AsyncXiaoboTask(retries=1) as tm:
    tm.submit_tasks_from_file(
        task_func=task_func,
        filename="example",  # 自动补全 .txt
    )
    await tm.wait()
```

配置项
-----
所有字段都可通过 `.env`、环境变量或构造参数设置（空字符串视为未设置）。

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `max_workers` | 5 | 最大并发数（线程/协程信号量） |
| `shuffle` | false | 提交前是否打乱任务顺序 |
| `retries` | 2 | 重试次数（`submit_task(s)` 参数可覆盖） |
| `retry_delay` | 0.0 | 重试间隔秒 |
| `proxy` | - | 代理地址，支持在字符串中用 `*****` 替换为数据预览 |
| `proxy_ipv6` | - | IPv6 代理 |
| `use_proxy_ipv6` | false | 优先使用 IPv6 代理 |
| `disable_proxy` | false | 禁用代理分配 |

回调与统计
---------
- 成功/失败/取消回调签名分别为 `(target, result|error)`，失败回调在所有重试耗尽后触发。
- `Target` 提供 `index`、`data`、`data_preview`、`proxy`、`logger` 等字段。
- 执行完调用 `statistics()` 查看成功/取消/失败计数及错误明细。

代理与会话辅助
-------------
- 代理模板示例：`http://user:pass@host:port` 或 `socks5://host:port`，若包含 `*****` 会用 `data_preview` 替换。
- 可直接获取带伪装的请求会话：`get_session()`、`get_async_session()`（基于 `curl-cffi`）。

运行示例
-------
- 同步示例：`python examples/example.py`
- 异步示例：`python examples/example_async.py`

开发提示
-------
- Python 版本要求 `>=3.13`
- 日志使用 `loguru`，初始化在包导入时完成，默认打印任务名称与色彩日志。
