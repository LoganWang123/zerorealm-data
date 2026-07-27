"""PublisherRegistry — 纯注册表.

只存储 Builder，不负责组装。
"""

from __future__ import annotations


class PublisherRegistry:
    """渠道 Builder 注册表."""

    _builders: dict[str, type] = {}

    @classmethod
    def register(cls, name: str):
        """装饰器：注册渠道 Builder."""

        def decorator(builder_cls):
            cls._builders[name] = builder_cls
            return builder_cls

        return decorator

    @classmethod
    def get_builder(cls, name: str):
        """获取渠道 Builder."""
        if name not in cls._builders:
            available = ", ".join(cls._builders.keys()) or "(none)"
            raise KeyError(f"Channel '{name}' not registered. Available: {available}")
        return cls._builders[name]

    @classmethod
    def list_channels(cls) -> list[str]:
        """列出所有已注册渠道."""
        return list(cls._builders.keys())
