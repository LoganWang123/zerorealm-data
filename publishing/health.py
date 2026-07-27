"""HealthChecker — 模块化健康检查 + 严重级."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path


class CheckSeverity(Enum):
    """检查严重级."""

    INFO = "info"  # 提示，不影响运行
    WARNING = "warning"  # 警告，仍可运行
    ERROR = "error"  # 错误，无法运行


class HealthCheck(ABC):
    """健康检查抽象."""

    name: str = "unnamed"

    @abstractmethod
    def check(self) -> tuple[CheckSeverity, str]:
        """执行检查，返回 (severity, message)."""
        ...


class ConfigCheck(HealthCheck):
    """配置文件检查."""

    name = "Config"

    def check(self) -> tuple[CheckSeverity, str]:
        path = Path("config/publish.yaml")
        if path.exists():
            return CheckSeverity.INFO, f"publish.yaml found"
        return CheckSeverity.ERROR, "config/publish.yaml not found"


class StorageCheck(HealthCheck):
    """存储目录检查."""

    name = "Storage"

    def check(self) -> tuple[CheckSeverity, str]:
        path = Path("storage/manifest")
        if path.exists() and path.is_dir():
            return CheckSeverity.INFO, "storage/manifest/ writable"
        return CheckSeverity.ERROR, "storage/manifest/ not found or not writable"


class CacheCheck(HealthCheck):
    """缓存目录检查."""

    name = "Cache"

    def check(self) -> tuple[CheckSeverity, str]:
        path = Path(".cache")
        if path.exists():
            return CheckSeverity.INFO, ".cache/ writable"
        # 尝试创建
        try:
            path.mkdir(parents=True, exist_ok=True)
            return CheckSeverity.INFO, ".cache/ created"
        except OSError:
            return CheckSeverity.WARNING, ".cache/ not writable"


class AssetCheck(HealthCheck):
    """素材检查."""

    name = "Assets"

    def check(self) -> tuple[CheckSeverity, str]:
        cover = Path("assets/covers/default.png")
        if cover.exists():
            return CheckSeverity.INFO, "default cover found"
        return CheckSeverity.WARNING, "default cover missing, will generate placeholder"


class HealthChecker:
    """健康检查器."""

    def __init__(self, checks: list[HealthCheck] | None = None):
        self.checks = checks or [
            ConfigCheck(),
            StorageCheck(),
            CacheCheck(),
            AssetCheck(),
        ]

    def run_all(self) -> list[tuple[str, CheckSeverity, str]]:
        """执行所有检查."""
        results = []
        for check in self.checks:
            severity, message = check.check()
            results.append((check.name, severity, message))
        return results

    def has_errors(self) -> bool:
        """是否有 ERROR 级问题."""
        return any(s == CheckSeverity.ERROR for _, s, _ in self.run_all())

    def print_report(self) -> None:
        """打印健康报告."""
        print("ZeroRealm CPP - Health Check")
        symbols = {
            CheckSeverity.INFO: "[OK]",
            CheckSeverity.WARNING: "[WARN]",
            CheckSeverity.ERROR: "[ERR]",
        }
        for name, severity, message in self.run_all():
            symbol = symbols[severity]
            print(f"  {symbol} {name}: {message}")
