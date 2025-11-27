# -*- coding: utf-8 -*-
from typing import Optional, Any

from pydantic import Field, field_validator
from pydantic_core.core_schema import FieldValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置模型，由 pydantic-settings 驱动。"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False  # 环境变量名不区分大小写
    )

    # --- 线程池配置 ---
    max_workers: int = Field(default=5, gt=0, description="最大线程数")

    # --- 任务执行配置 ---
    shuffle: bool = Field(default=False, description="打乱任务顺序")
    retries: int = Field(default=2, ge=0, description="重试次数")
    retry_delay: float = Field(default=0.0, ge=0, description="重试延迟（秒）")

    # --- 代理配置 ---
    proxy: Optional[str] = Field(default=None, description="代理")
    proxy_ipv6: Optional[str] = Field(default=None, description="IPv6代理")
    use_proxy_ipv6: bool = Field(default=False, description="使用IPv6代理")
    disable_proxy: bool = Field(default=False, description="禁用代理")

    @field_validator('*', mode='before')
    @classmethod
    def empty_str_to_default(cls, v: Any, info: FieldValidationInfo) -> Any:
        """在验证前，将空字符串转换成该字段的默认值。"""
        if v == "":
            return cls.model_fields[info.field_name].default
        return v
