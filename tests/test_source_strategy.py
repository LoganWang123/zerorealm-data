from crawlers.base import BaseCrawler
from generators.daily_report import select_editorial_candidates
import yaml
from pathlib import Path


class StubCrawler(BaseCrawler):
    async def fetch(self):
        return []


def test_crawler_preserves_industry_role_and_priority_in_every_item():
    crawler = StubCrawler(
        {
            "id": "operator_source",
            "name": "Operator Source",
            "url": "https://example.com/news",
            "type": "web",
            "industry_role": "operator",
            "industry_segment": "smart_vending",
            "priority": "P0",
            "score": 95,
        },
        "run-1",
    )

    item = crawler._make_item(
        title="运营商新增智能柜点位",
        url="https://example.com/news/1",
    )

    assert item.metadata["industry_role"] == "operator"
    assert item.metadata["industry_segment"] == "smart_vending"
    assert item.metadata["source_priority"] == "P0"
    assert item.metadata["source_name"] == "Operator Source"


def test_editorial_candidates_put_direct_industry_sources_before_general_media():
    items = [
        {
            "source": f"media-{index}",
            "title": f"综合新闻{index}",
            "metadata": {"industry_role": "media", "boost_score": 20},
        }
        for index in range(20)
    ]
    items.extend(
        [
            {
                "source": "ubox",
                "title": "友宝运营动态",
                "metadata": {
                    "industry_role": "operator",
                    "source_priority": "P0",
                    "boost_score": 8,
                },
            },
            {
                "source": "vendor",
                "title": "设备商发布补货能力",
                "metadata": {
                    "industry_role": "vendor",
                    "source_priority": "P0",
                    "boost_score": 7,
                },
            },
        ]
    )

    selected = select_editorial_candidates(items, max_items=12, max_media=4)

    assert [item["source"] for item in selected[:2]] == ["ubox", "vendor"]
    assert sum(
        item["metadata"].get("industry_role") == "media" for item in selected
    ) <= 4


def test_source_registry_covers_core_operators_vendors_and_beverage_brands():
    config = yaml.safe_load(
        (Path(__file__).parents[1] / "config" / "sources.yaml").read_text(
            encoding="utf-8"
        )
    )
    active = {
        source["id"]: source
        for source in config["sources"]
        if source.get("enabled", True)
    }

    assert active["eastroc_web"]["industry_role"] == "brand"
    assert active["hetun_web"]["industry_role"] == "vendor"
    assert active["easivend_web"]["industry_role"] == "vendor"
    assert active["zhongji_web"]["url"] == "https://www.t-cn.com/"
