"""Discovery v1.1: source quality, freshness, ranking, research review queue."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from crawlers.base import RawItem
from discovery.freshness import freshness_score, parse_published_at, resolve_discovery_published_at
from discovery.models import CandidateStatus, SearchCandidate
from discovery.pipeline import DiscoveryPipeline, DiscoveryPipelineConfig
from discovery.pool import CandidatePool
from discovery.queries import resolve_queries
from discovery.review_queue import ResearchReviewQueue, ReviewStatus
from discovery.scoring import score_candidate
from discovery.source_quality import SourceTier, SourceType, classify_source
from research.models import ClaimStatus
from utils.helpers import generate_id, now_iso


class FakeSearchProvider:
    name = "fake"

    def __init__(self, candidates: list[SearchCandidate]):
        self._candidates = candidates

    def search(self, query: str, *, limit: int = 10, **_kwargs) -> list[SearchCandidate]:
        del query
        return list(self._candidates)[:limit]


def _candidate(
    *,
    url: str,
    title: str = "智能柜投放扩大",
    query: str = "智能柜",
    rank: int = 1,
    snippet: str = "智能柜相关摘要",
) -> SearchCandidate:
    return SearchCandidate(
        provider="fake",
        query=query,
        title=title,
        url=url,
        snippet=snippet,
        provider_content="must-not-become-evidence",
        rank=rank,
        discovered_at="2026-08-08T10:00:00+08:00",
        language="zh-CN",
        evidence_eligible=False,
    )


def _raw(
    *,
    url: str,
    title: str,
    content_text: str,
    published_at: str | None = "2026-08-07T09:00:00+08:00",
) -> RawItem:
    return RawItem(
        id=generate_id("discovery:fake", url),
        source="discovery:fake",
        source_type="web",
        language="zh-CN",
        title=title,
        url=url,
        published_at=published_at or "",
        crawled_at=now_iso(),
        run_id="test_run",
        crawl_status="ok",
        http_status=200,
        content_html=f"<p>{content_text}</p>",
        content_text=content_text,
        summary=content_text[:80],
        author="",
        tags=[],
        metadata={},
    )


def test_source_classification_tiers():
    cases = [
        ("https://www.gov.cn/zhengce/content/2026.htm", SourceType.GOVERNMENT, SourceTier.S),
        ("https://www.cninfo.com.cn/new/disclosure/detail", SourceType.EXCHANGE, SourceTier.S),
        ("https://www.caixin.com/2026-08-01/123.html", SourceType.MAJOR_MEDIA, SourceTier.A),
        ("https://vendor.example.com/product", SourceType.VENDOR, SourceTier.C),
        ("https://zh.wikipedia.org/wiki/自动售货机", SourceType.ENCYCLOPEDIA, SourceTier.C),
        ("https://random-blog.example.org/post/1", SourceType.UNKNOWN, SourceTier.C),
    ]
    for url, expected_type, expected_tier in cases:
        title = "官网 产品中心" if expected_type is SourceType.VENDOR else "标题"
        clf = classify_source(url, title=title)
        assert clf.source_type is expected_type, url
        assert clf.source_tier is expected_tier, url


def test_freshness_recent_beats_old_and_unknown_not_today():
    now = datetime(2026, 8, 8, tzinfo=timezone.utc)
    recent = freshness_score("2026-08-07T00:00:00+00:00", intent="daily", now=now)
    old = freshness_score("2023-01-01T00:00:00+00:00", intent="daily", now=now)
    unknown = freshness_score(None, intent="daily", now=now)
    assert recent > old
    assert unknown == 5.0
    assert parse_published_at(None) is None
    assert parse_published_at("unknown") is None
    # Crawler often fills published_at with crawl time when page has no date.
    assert (
        resolve_discovery_published_at(
            "2026-08-08T12:00:00+08:00",
            crawled_at="2026-08-08T12:00:01+08:00",
            discovered_at="2026-08-08T12:00:00+08:00",
        )
        is None
    )
    assert (
        resolve_discovery_published_at(
            "2023-02-14T00:00:00+08:00",
            crawled_at="2026-08-08T12:00:00+08:00",
        )
        == "2023-02-14T00:00:00+08:00"
    )


def test_ranking_prefers_official_recent_over_old_aggregator():
    official = _candidate(
        url="https://www.cninfo.com.cn/new/disclosure/detail?id=1",
        title="上市公司智能柜相关公告",
        rank=2,
    )
    aggregator = _candidate(
        url="https://www.sohu.com/a/old-agg",
        title="智能柜转载汇总",
        rank=1,
    )
    official_score = score_candidate(
        official,
        published_at="2026-08-07T00:00:00+00:00",
        intent="research",
    )
    aggregator_score = score_candidate(
        aggregator,
        published_at="2023-01-01T00:00:00+00:00",
        intent="research",
    )
    assert official_score > aggregator_score


def test_verified_enters_review_queue_once(tmp_path: Path):
    url = "https://example.com/story"
    cand = _candidate(url=url)
    body = "公司宣布扩大智能柜投放，正文足够用于研究验证。"
    pool_path = tmp_path / "pool.json"
    queue_path = tmp_path / "queue.json"

    def fetch(u: str) -> RawItem:
        return _raw(url=u, title=cand.title, content_text=body)

    pipe = DiscoveryPipeline(
        provider=FakeSearchProvider([cand]),
        pool=CandidatePool(pool_path),
        review_queue=ResearchReviewQueue(queue_path),
        fetcher=fetch,
        config=DiscoveryPipelineConfig(
            persist=True,
            pool_path=str(pool_path),
            queue_path=str(queue_path),
        ),
    )
    first = pipe.run("智能柜", limit=1)[0]
    assert first.status is CandidateStatus.VERIFIED
    assert first.review_queue_id
    assert all(s == ClaimStatus.DRAFT.value for s in first.metadata.get("claims_status", []))

    queue = ResearchReviewQueue.load_or_create(queue_path)
    assert len(queue.all()) == 1
    assert queue.all()[0].review_status is ReviewStatus.PENDING

    pipe2 = DiscoveryPipeline(
        provider=FakeSearchProvider([cand]),
        pool=CandidatePool.load_or_create(pool_path),
        review_queue=ResearchReviewQueue.load_or_create(queue_path),
        fetcher=lambda _u: (_ for _ in ()).throw(AssertionError("no refetch")),
        config=DiscoveryPipelineConfig(
            persist=True,
            pool_path=str(pool_path),
            queue_path=str(queue_path),
        ),
    )
    second = pipe2.run("智能柜", limit=1)[0]
    assert second.candidate_id == first.candidate_id
    queue2 = ResearchReviewQueue.load_or_create(queue_path)
    assert len(queue2.all()) == 1


def test_rejected_does_not_enter_review_queue(tmp_path: Path):
    from discovery.fetch import FetchResult

    url = "https://example.com/empty"
    pipe = DiscoveryPipeline(
        provider=FakeSearchProvider([_candidate(url=url)]),
        pool=CandidatePool(tmp_path / "pool.json"),
        review_queue=ResearchReviewQueue(tmp_path / "queue.json"),
        fetcher=lambda u: FetchResult(
            item=_raw(url=u, title="空", content_text="   "),
            method="html",
            ok=True,
        ),
        config=DiscoveryPipelineConfig(
            persist=False,
            pool_path=str(tmp_path / "pool.json"),
            queue_path=str(tmp_path / "queue.json"),
        ),
    )
    record = pipe.run("智能柜", limit=1)[0]
    assert record.status is CandidateStatus.REJECTED
    assert pipe.review_queue.all() == []


def test_review_approve_reject_defer(tmp_path: Path):
    queue_path = tmp_path / "queue.json"
    url = "https://www.caixin.com/2026/a.html"
    cand = _candidate(url=url, title="主流媒体智能柜报道")
    body = "主流财经媒体报道智能柜行业动态，正文足够验证。"
    pipe = DiscoveryPipeline(
        provider=FakeSearchProvider([cand]),
        pool=CandidatePool(tmp_path / "pool.json"),
        review_queue=ResearchReviewQueue(queue_path),
        fetcher=lambda u: _raw(url=u, title=cand.title, content_text=body),
        config=DiscoveryPipelineConfig(
            persist=True,
            pool_path=str(tmp_path / "pool.json"),
            queue_path=str(queue_path),
        ),
    )
    record = pipe.run("智能柜", limit=1)[0]
    qid = record.review_queue_id
    assert qid

    queue = ResearchReviewQueue.load_or_create(queue_path)
    assert queue.set_status(qid, ReviewStatus.APPROVED, reason="worth research").review_status is (
        ReviewStatus.APPROVED
    )
    assert queue.set_status(qid, ReviewStatus.REJECTED, reason="noise").review_status is (
        ReviewStatus.REJECTED
    )
    assert queue.set_status(qid, ReviewStatus.DEFERRED, reason="later").review_status is (
        ReviewStatus.DEFERRED
    )
    # Approve does not flip ClaimStatus
    assert all(s == ClaimStatus.DRAFT.value for s in record.metadata.get("claims_status", []))


def test_published_at_unknown_not_filled_with_discovered_at(tmp_path: Path):
    url = "https://example.com/no-date"
    cand = _candidate(url=url)
    body = "页面没有可解析发布日期，但正文足够进入研究证据层。"
    pipe = DiscoveryPipeline(
        provider=FakeSearchProvider([cand]),
        pool=CandidatePool(tmp_path / "pool.json"),
        review_queue=ResearchReviewQueue(tmp_path / "queue.json"),
        fetcher=lambda u: _raw(url=u, title=cand.title, content_text=body, published_at=None),
        config=DiscoveryPipelineConfig(
            persist=False,
            pool_path=str(tmp_path / "pool.json"),
            queue_path=str(tmp_path / "queue.json"),
        ),
    )
    record = pipe.run("智能柜", limit=1)[0]
    assert record.status is CandidateStatus.VERIFIED
    assert record.published_at is None
    assert record.published_at != record.candidate.discovered_at
    assert record.freshness_score == 5.0


def test_query_registry_intents_and_topics():
    registry = {
        "max_queries_per_run": 3,
        "defaults": {"intent": "research", "freshness_window": None},
        "topics": {
            "smart-cabinet": {
                "label": "智能柜",
                "intent": "research",
                "queries": ["智能柜", "智能货柜", "无人零售", "自动售货机"],
            },
            "instant-retail": {
                "label": "即时零售",
                "intent": "insight",
                "freshness_window": "30d",
                "queries": ["即时零售", "即时电商"],
            },
        },
        "company_query_templates": [
            "{company} 智能柜",
            "{company} 无人零售",
            "{company} 自动售货",
            "{company} AI",
        ],
        "companies": [{"name": "友宝", "intent": "research", "freshness_window": "180d"}],
    }
    topic = resolve_queries(topic="smart-cabinet", registry=registry)
    assert topic.intent == "research"
    assert len(topic.queries) == 3
    insight = resolve_queries(topic="instant-retail", registry=registry)
    assert insight.intent == "insight"
    assert insight.freshness_window == "30d"
    company = resolve_queries(company="友宝", registry=registry)
    assert company.company_terms == ["友宝"]
    assert company.queries[0] == "友宝 智能柜"
