"""
通用异步多线程任务框架

该模块提供了一个简单易用的异步任务管理器，允许调用者提交任务并在任务完成或失败时执行回调。
"""
import sys

from dotenv import load_dotenv
from loguru import logger

from .domain import Target
from .exceptions import TaskFailed
from .facade import XiaoboTask, AsyncXiaoboTask
from .manager import TaskManager, AsyncTaskManager
from .util import (
    read_txt_file_lines,
    write_txt_file,
    get_session,
    get_async_session,
    raise_response_error,
    parse_cloudflare_error,
    json_get,
)

__version__ = '1.0.6'

__all__ = [
    'Target',
    'TaskManager',
    'AsyncTaskManager',
    'TaskFailed',
    'XiaoboTask',
    'AsyncXiaoboTask',
    'read_txt_file_lines',
    'write_txt_file',
    'get_session',
    'get_async_session',
    'raise_response_error',
    'parse_cloudflare_error',
    'json_get',
]

# 自动加载 .env 文件
load_dotenv()

# --- 日志配置 ---
# 移除默认的 logger，添加自定义格式的 logger
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <7}</level> | <cyan>[{extra[name]}]</cyan> - <level>{message}</level>",
    colorize=True,
    backtrace=False
)
logger.configure(extra={"name": "MainApp"})
