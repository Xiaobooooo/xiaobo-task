# -*- coding: utf-8 -*-
"""
通用工具模块
"""
import asyncio
import threading
from typing import List, Optional
from pathlib import Path
import sys

from curl_cffi import BrowserTypeLiteral, Session, AsyncSession
from curl_cffi.requests.impersonate import DEFAULT_CHROME

# 使用线程本地存储为每个线程维护一个独立的事件循环
_thread_local = threading.local()


def _resolve_txt_path(filename: str) -> Path:
    """补全 .txt 后缀并将相对路径定位到脚本入口所在的目录。"""
    if not filename.lower().endswith('.txt'):
        filename += '.txt'

    path = Path(filename)
    if not path.is_absolute():
        entry_dir = Path(sys.argv[0]).resolve().parent
        path = entry_dir / path
    return path


def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """获取或创建当前线程的事件循环。"""
    if not hasattr(_thread_local, "loop"):
        _thread_local.loop = asyncio.new_event_loop()
    return _thread_local.loop


def read_txt_file_lines(filename: str) -> List[str]:
    """
    读取txt文件内容并按行返回一个列表。

    功能:
    - 如果文件名没有 .txt 后缀(不区分大小写)，会自动补全。
    - 按行读取文件，并去除每行两侧的空白字符（包括换行符）。
    - 返回一个包含文件中所有非空行的字符串列表。

    :param filename: 要读取的txt文件名。
    :return: 包含文件所有行的字符串列表。
    :raises FileNotFoundError: 如果文件未找到。
    :raises IOError: 如果发生其他读取错误。
    """
    path = _resolve_txt_path(filename)

    try:
        with open(path, 'r', encoding='utf-8') as f:
            # 使用列表推导式高效读取，并只保留非空行
            lines = [line.strip() for line in f if line.strip()]
        return lines
    except FileNotFoundError:
        raise FileNotFoundError(f"错误：文件 '{path}' 未找到。")
    except Exception as e:
        raise IOError(f"读取文件 '{path}' 时发生错误: {e}")


def write_txt_file(filename: str, data: str | List[str], append: bool = True, separator: str = "----") -> None:
    """
    写入或追加文本到txt文件。

    功能:
    - 自动补全 .txt 后缀（不区分大小写）。
    - data 支持字符串或字符串列表，列表会用分隔符拼接后写入。
    - append 为 True 时追加写入，否则覆盖写入，默认 True。
    - separator 控制列表拼接时的分隔符，默认 "----"。

    :param filename: 目标文件名。
    :param data: 要写入的内容，字符串或字符串列表。
    :param append: 是否追加写入。
    :param separator: data 为列表时的拼接分隔符。
    """
    path = _resolve_txt_path(filename)

    text = separator.join(data) if isinstance(data, list) else str(data)
    if text and not text.endswith('\n'):
        text += '\n'

    mode = 'a' if append else 'w'
    with open(path, mode, encoding='utf-8') as f:
        f.write(text)


def get_session(proxy: str = None, timeout: int = 30, impersonate: Optional[BrowserTypeLiteral] = DEFAULT_CHROME):
    return Session(proxy=proxy, timeout=timeout, impersonate=impersonate)


def get_async_session(proxy: str = None, timeout: int = 30, impersonate: Optional[BrowserTypeLiteral] = DEFAULT_CHROME):
    return AsyncSession(proxy=proxy, timeout=timeout, impersonate=impersonate)
