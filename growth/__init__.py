"""Channel growth report parsing, baselines, and founder ops."""

from growth.baseline import build_channel_baseline, render_baseline_markdown
from growth.combat_pack import build_combat_pack
from growth.ledger import compute_funnel_rates, default_ledger_template, validate_ledger
from growth.ops import generate_founder_growth_ops
from growth.scorecard import build_founder_scorecard
from growth.wechat import parse_wechat_tendency_xls
from growth.zhihu import parse_zhihu_daily_csv

__all__ = [
    "build_channel_baseline",
    "build_combat_pack",
    "build_founder_scorecard",
    "compute_funnel_rates",
    "default_ledger_template",
    "generate_founder_growth_ops",
    "parse_wechat_tendency_xls",
    "parse_zhihu_daily_csv",
    "render_baseline_markdown",
    "validate_ledger",
]
