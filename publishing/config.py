"""PublishConfig 配置模型.

支持基础配置 + 环境覆盖（publish.yaml + publish.dev.yaml）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class WechatConfig:
    """微信公众号配置."""

    title_prefix: str = "零域日报"
    author: str = "ZeroRealm AI"
    copyright: str = "原创"
    digest_source: str = "summary"
    app_id: str = ""  # 从 .env 读取
    app_secret: str = ""  # 从 .env 读取


@dataclass
class CoverConfig:
    """封面配置."""

    width: int = 900
    height: int = 383
    bg_color: str = "#1a1a2e"
    accent_color: str = "#4a90d9"
    font: str = "assets/fonts/NotoSansSC-Bold.otf"


@dataclass
class PipelineConfig:
    """Pipeline 配置."""

    validate: bool = True
    retry: int = 3
    retry_backoff: list[int] = field(default_factory=lambda: [1, 2, 4])


@dataclass
class LoggingConfig:
    """日志配置."""

    dir: str = "logs"
    format: str = "json"


@dataclass
class PublishConfig:
    """发布平台总配置."""

    wechat: WechatConfig = field(default_factory=WechatConfig)
    cover: CoverConfig = field(default_factory=CoverConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def load(
        cls,
        path: str = "config/publish.yaml",
        override: str | None = None,
    ) -> PublishConfig:
        """加载基础配置 + 可选环境覆盖."""
        data = cls._load_yaml(path)
        if override:
            override_data = cls._load_yaml(override)
            data = cls._deep_merge(data, override_data)
        return cls._from_dict(data)

    @staticmethod
    def _load_yaml(path: str) -> dict:
        p = Path(path)
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """递归合并，override 优先."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = PublishConfig._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    @classmethod
    def _from_dict(cls, data: dict) -> PublishConfig:
        wechat_data = data.get("wechat", {})
        cover_data = data.get("cover", {})
        pipeline_data = data.get("pipeline", {})
        logging_data = data.get("logging", {})

        return cls(
            wechat=WechatConfig(**wechat_data),
            cover=CoverConfig(**cover_data),
            pipeline=PipelineConfig(**pipeline_data),
            logging=LoggingConfig(**logging_data),
        )
