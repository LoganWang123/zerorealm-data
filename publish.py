"""ZeroRealm Content Publishing Platform — CLI 入口.

Usage:
    python publish.py --channel wechat
    python publish.py --channel wechat --dry-run
    python publish.py --channel wechat --preview
    python publish.py --channel wechat --date 2026-07-26
    python publish.py --list
    python publish.py --check
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).parent))
load_dotenv(Path(__file__).parent / ".env")

# 注册渠道（import 即注册）
import publishing.wechat.builder  # noqa: F401
from publishing.asset_manager import AssetManager
from publishing.config import PublishConfig
from publishing.factory import BuilderContext, PublisherFactory
from publishing.health import HealthChecker
from publishing.manifest_repository import ManifestRepository
from publishing.models import RenderContext
from publishing.registry import PublisherRegistry
from publishing.workflow import PublishWorkflow


def setup_logging(config: PublishConfig) -> logging.Logger:
    """配置日志."""
    log_dir = Path(config.logging.dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("publishing")
    logger.setLevel(logging.INFO)

    # 控制台
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(console)

    # 文件
    from datetime import datetime

    log_file = log_dir / f"publish_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(file_handler)

    return logger


def find_article(date_str: str) -> str:
    """查找指定日期的文章文件."""
    path = Path(f"output_daily/{date_str}.mdx")
    if path.exists():
        return str(path)
    raise FileNotFoundError(f"Article not found: {path}")


def cmd_list():
    """列出所有已注册渠道."""
    channels = PublisherRegistry.list_channels()
    print("Registered channels:")
    descriptions = {
        "wechat": "微信公众号（草稿/发布）",
        "website": "官网（git push）[coming soon]",
    }
    for ch in channels:
        desc = descriptions.get(ch, "")
        print(f"  {ch:<12}{desc}")


def cmd_check():
    """健康检查."""
    checker = HealthChecker()
    checker.print_report()


def cmd_publish(args):
    """执行发布流程."""
    # 加载配置
    config = PublishConfig.load(
        path=args.config,
        override=args.override,
    )
    logger = setup_logging(config)

    # 确定日期
    date_str = args.date or date.today().isoformat()

    # 查找文章
    try:
        article_path = find_article(date_str)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    # 确定模式
    if args.dry_run:
        mode = "dry_run"
    elif args.preview:
        mode = "preview"
    elif args.notify_followers:
        mode = "notify"
    elif args.publish:
        mode = "publish"
    else:
        mode = "draft"

    # 初始化基础设施
    manifest = ManifestRepository()
    asset_manager = AssetManager()

    # 构建 RenderContext
    render_context = RenderContext(
        config=config,
        asset_manager=asset_manager,
        preview=args.preview,
        environment="dev" if args.dry_run else "prod",
    )

    # 逐渠道发布
    channels = [ch.strip() for ch in args.channel.split(",")]
    for channel in channels:
        logger.info("=" * 50)
        logger.info("Channel: %s | Mode: %s | Date: %s", channel, mode, date_str)
        logger.info("=" * 50)

        # Factory 组装 ChannelTarget
        builder_ctx = BuilderContext(
            config=config,
            mode=mode,
            manifest=manifest,
            logger=logger,
        )
        target = PublisherFactory.create(channel, builder_ctx)

        # Workflow 执行
        workflow = PublishWorkflow(config=config, manifest=manifest, logger=logger)
        result = workflow.run(article_path, target, render_context, mode=mode)

        # 输出结果
        if result:
            logger.info(
                "Result: status=%s channel=%s message=%s duration=%.2fs",
                result.status.value,
                result.channel,
                result.message,
                result.duration,
            )
            if result.draft_id:
                logger.info("Draft ID: %s", result.draft_id)
        else:
            logger.warning("No result returned")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser with mutually exclusive delivery modes."""
    parser = argparse.ArgumentParser(
        description="ZeroRealm Content Publishing Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--channel", "-c", help="目标渠道（逗号分隔多渠道）")
    parser.add_argument("--date", "-d", help="指定日期（YYYY-MM-DD）")
    parser.add_argument("--config", default="config/publish.yaml", help="配置文件路径")
    parser.add_argument("--override", help="环境覆盖配置")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="演练模式（不调 API）")
    mode.add_argument("--preview", action="store_true", help="预览模式（输出 HTML）")
    mode.add_argument(
        "--publish",
        action="store_true",
        help="自由发表（不会向关注者发送通知）",
    )
    mode.add_argument(
        "--notify-followers",
        action="store_true",
        help="群发通知给全部关注者（会产生真实外部发送）",
    )
    parser.add_argument("--resume", action="store_true", help="从失败处继续")
    parser.add_argument("--list", action="store_true", help="列出已注册渠道")
    parser.add_argument("--check", action="store_true", help="健康检查")

    return parser


def main():
    """CLI 主入口."""
    parser = build_parser()
    args = parser.parse_args()

    if args.list:
        cmd_list()
        return

    if args.check:
        cmd_check()
        return

    if not args.channel:
        parser.print_help()
        sys.exit(1)

    cmd_publish(args)


if __name__ == "__main__":
    main()
