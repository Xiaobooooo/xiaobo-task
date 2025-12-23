# -*- coding: utf-8 -*-

from dataclasses import dataclass
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger


@dataclass
class Target:
    """任务数据源的封装。

    用于将任务的索引和相关数据作为一个单元传递给任务函数。

    属性:
        index (int): 任务在其批次中的索引（从0开始）。
        data (Any): 与任务关联的数据。
        data_preview (Optional[str]): 用于显示的数据。
        proxy (Optional[Proxy]): 分配给此任务的代理。
        logger (Optional["Logger"]): 分配给此任务的日志记录器实例。
    """
    index: int
    data: Any
    data_preview: str
    logger: Optional["Logger"] = None
    proxy: Optional[str] = None

    def refresh_proxy(self):
        return self.proxy

