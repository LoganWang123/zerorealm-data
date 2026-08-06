"""ZeroRealm Daily Pipeline — 一条命令完成本地采集与生成.

Usage:
    python run_daily.py                # 采集 + 生成日报 + 本地复制到网站目录（默认不 push）
    python run_daily.py --skip-crawl   # 跳过采集（用已有数据生成日报）
    python run_daily.py --date 2026-07-27
    python run_daily.py --push-website # 显式启用本地 git push 网站仓库
    python run_daily.py --no-push      # 兼容旧参数：保持不推送（默认已是不推送）

流程：
    1. 采集（main.py）
    2. 生成日报（generate_daily.py）
    3. 同步到本地官网目录（copy → zerorealm-website/content/daily/）
    4. 仅在 --push-website 时：Git commit + push 官网（触发 Vercel 部署）

跨仓库自动同步以 GitHub Actions 为准；本地 push 仅为过渡期逃生舱。
"""

import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Paths
DATA_DIR = Path(__file__).parent
WEBSITE_DIR = DATA_DIR.parent / "zerorealm-website"
WEBSITE_CONTENT_DIR = WEBSITE_DIR / "content" / "daily"

CST = timezone(timedelta(hours=8))


def log(msg: str):
    print(f"\n{'='*60}\n  {msg}\n{'='*60}")


def run_cmd(cmd: list[str], cwd: str | None = None) -> int:
    """Run a subprocess command, return exit code."""
    print(f"  > {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd or str(DATA_DIR))
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for the local daily pipeline."""
    parser = argparse.ArgumentParser(
        description="ZeroRealm Daily Pipeline — 本地采集/生成（默认不 push 官网）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--date", type=str, help="指定日期 (YYYY-MM-DD)，默认今天")
    parser.add_argument("--skip-crawl", action="store_true", help="跳过采集步骤")
    parser.add_argument(
        "--push-website",
        action="store_true",
        help="显式启用本地 git push 网站仓库（默认关闭）",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="兼容旧参数：不推送官网（默认已是不推送）",
    )
    return parser


def should_push_website(args: argparse.Namespace) -> bool:
    """Return True only when local website push is explicitly requested."""
    return bool(args.push_website) and not bool(args.no_push)


def step_crawl() -> bool:
    """Step 1: Run crawler."""
    log("Step 1/4: 采集数据")
    code = run_cmd([sys.executable, "main.py"])
    if code != 0:
        print("  ⚠️  采集有警告，继续执行...")
    return True


def step_generate(date: str) -> str | None:
    """Step 2: Generate daily report. Returns output path."""
    log(f"Step 2/4: 生成日报 ({date})")
    code = run_cmd([sys.executable, "generate_daily.py", "--date", date])
    if code != 0:
        print("  ❌ 日报生成失败")
        return None

    output_path = DATA_DIR / "output_daily" / f"{date}.mdx"
    if output_path.exists():
        print(f"  ✅ 日报已生成: {output_path}")
        return str(output_path)
    else:
        print(f"  ❌ 输出文件不存在: {output_path}")
        return None


def step_sync_website(date: str, source_path: str) -> bool:
    """Step 3: Copy MDX to website content directory."""
    log("Step 3/4: 同步到本地官网目录")

    if not WEBSITE_DIR.exists():
        print(f"  ❌ 官网目录不存在: {WEBSITE_DIR}")
        return False

    WEBSITE_CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    dest = WEBSITE_CONTENT_DIR / f"{date}.mdx"
    shutil.copy2(source_path, dest)
    print(f"  ✅ 已复制: {dest}")
    return True


def step_push_website(date: str) -> bool:
    """Step 4: Git commit + push website (triggers Vercel deploy)."""
    log("Step 4/4: 推送官网 (触发 Vercel 部署)")

    website = str(WEBSITE_DIR)

    # git add
    code = run_cmd(["git", "add", f"content/daily/{date}.mdx"], cwd=website)
    if code != 0:
        print("  ❌ git add 失败")
        return False

    # Check if there's something to commit
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=website, capture_output=True,
    )
    if result.returncode == 0:
        print("  ℹ️  无变更，跳过提交")
        return True

    # git commit
    code = run_cmd(
        ["git", "commit", "-m", f"feat(daily): 零域日报 {date}"],
        cwd=website,
    )
    if code != 0:
        print("  ❌ git commit 失败")
        return False

    # git push
    code = run_cmd(["git", "push"], cwd=website)
    if code != 0:
        print("  ❌ git push 失败")
        return False

    print("  ✅ 已推送，Vercel 将在 1~2 分钟内更新")
    return True


def main():
    parser = build_parser()
    args = parser.parse_args()

    date = args.date or datetime.now(CST).strftime("%Y-%m-%d")
    push_website = should_push_website(args)

    print(f"\n🚀 ZeroRealm Daily Pipeline — {date}")
    print(f"   数据目录: {DATA_DIR}")
    print(f"   官网目录: {WEBSITE_DIR}")
    print(f"   本地推送: {'开启 (--push-website)' if push_website else '关闭（默认）'}")

    # Step 1: Crawl
    if not args.skip_crawl:
        step_crawl()
    else:
        log("Step 1/4: 跳过采集 (--skip-crawl)")

    # Step 2: Generate
    output_path = step_generate(date)
    if not output_path:
        print("\n❌ 管线中断：日报生成失败")
        sys.exit(1)

    # Step 3: Sync to website
    if not step_sync_website(date, output_path):
        print("\n❌ 管线中断：同步官网失败")
        sys.exit(1)

    # Step 4: Push only when explicitly requested
    if push_website:
        step_push_website(date)
    else:
        log("Step 4/4: 跳过推送（默认不 push；需要时加 --push-website）")

    # Done
    log("✅ 全流程完成")
    print(f"   日报: output_daily/{date}.mdx")
    print(f"   官网: content/daily/{date}.mdx")
    if push_website:
        print("   部署: Vercel 自动更新中...")
    else:
        print("   部署: 未推送；自动同步请使用 GitHub Actions")
    print()


if __name__ == "__main__":
    main()
