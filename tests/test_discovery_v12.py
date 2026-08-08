"""Discovery v1.2 + Human Claim Review + Verified Export tests."""

from __future__ import annotations

from pathlib import Path

from crawlers.base import RawItem
from discovery.clustering import assign_clusters, title_similarity
from discovery.fetch import FetchResult, classify_fetch_exception, fetch_with_fallback
from discovery.models import CandidateStatus, SearchCandidate
from discovery.pipeline import DiscoveryPipeline, DiscoveryPipelineConfig
from discovery.pool import CandidatePool
from discovery.publication_date import extract_publication_dates
from discovery.queries import resolve_batch_topics
from discovery.review_queue import ResearchReviewQueue, ReviewStatus
from discovery.source_quality import SourceTier, SourceType, classify_source, clear_source_quality_cache
from research.atom_store import ResearchAtomStore
from research.claim_review import ClaimReviewError, set_claim_status
from research.exporters.verified_research import export_verified_research
from research.intake import news_to_research_atoms
from research.models import ClaimStatus
from utils.helpers import generate_id, now_iso


class FakeSearchProvider:
    name = "fake"

    def __init__(self, candidates: list[SearchCandidate]):
        self._candidates = candidates

    def search(self, query: str, *, limit: int = 10, **_kwargs) -> list[SearchCandidate]:
        del query
        return list(self._candidates)[:limit]


def _candidate(url: str, title: str = "智能柜投放扩大", rank: int = 1) -> SearchCandidate:
    return SearchCandidate(
        provider="fake",
        query="智能柜",
        title=title,
        url=url,
        snippet="智能柜相关摘要",
        provider_content="must-not-become-evidence",
        rank=rank,
        discovered_at="2026-08-08T10:00:00+08:00",
        language="zh-CN",
        evidence_eligible=False,
    )


def _raw(url: str, title: str, content_text: str, html: str = "", published_at: str = "") -> RawItem:
    return RawItem(
        id=generate_id("discovery:fake", url),
        source="discovery:fake",
        source_type="web",
        language="zh-CN",
        title=title,
        url=url,
        published_at=published_at or now_iso(),
        crawled_at=now_iso(),
        run_id="test_run",
        crawl_status="ok",
        http_status=200,
        content_html=html or f"<p>{content_text}</p>",
        content_text=content_text,
        summary=content_text[:80],
        author="",
        tags=[],
        metadata={},
    )


def test_publication_date_jsonld_and_meta_and_chinese():
    html = """
    <html><head>
      <script type="application/ld+json">
      {"@type":"NewsArticle","datePublished":"2026-08-01T08:00:00+08:00",
       "dateModified":"2026-08-03T09:00:00+08:00","publisher":{"name":"财新"}}
      </script>
      <meta property="article:published_time" content="2026-08-02T10:00:00+08:00"/>
      <meta property="og:site_name" content="Caixin"/>
    </head><body>
      <time datetime="2026-07-30">July 30</time>
      <p>发布时间：2026年08月04日 12:00</p>
      <p>更新时间：2026年08月05日 08:00</p>
    </body></html>
    """
    result = extract_publication_dates(html)
    assert result.published_at.startswith("2026-08-01")
    assert result.published_at_source == "jsonld.datePublished"
    assert result.modified_at.startswith("2026-08-03")
    assert result.modified_at_source == "jsonld.dateModified"
    assert result.date_conflict is True
    assert "PUBLICATION_DATE_CONFLICT" in result.warnings


def test_publication_date_unknown_stays_null_and_not_crawl_time():
    result = extract_publication_dates("<html><body><p>no dates here</p></body></html>")
    assert result.published_at is None
    assert result.published_at_source == "unknown"


def test_source_quality_registry_and_unknown(tmp_path: Path):
    clear_source_quality_cache()
    clf = classify_source("https://www.cninfo.com.cn/new/disclosure/detail")
    assert clf.source_type is SourceType.EXCHANGE
    assert clf.source_tier is SourceTier.S
    assert "巨潮" in clf.publisher
    unknown = classify_source("https://random-blog.example.org/x")
    assert unknown.source_type is SourceType.UNKNOWN
    assert unknown.source_tier is SourceTier.C
    wiki = classify_source("https://zh.wikipedia.org/wiki/Foo")
    assert wiki.source_type is SourceType.ENCYCLOPEDIA
    clear_source_quality_cache()


def test_syndication_cluster_penalizes_secondary():
    official = _candidate(
        "https://www.cninfo.com.cn/a/1",
        title="某某公司智能柜相关公告",
        rank=2,
    )
    copy = _candidate(
        "https://www.sohu.com/a/2",
        title="某某公司智能柜相关公告",
        rank=1,
    )
    assert title_similarity(official.title, copy.title) > 0.8
    clusters = assign_clusters([official, copy])
    assert clusters[official.url].source_role.value in {"original", "unique"}
    assert clusters[copy.url].syndication_penalty >= 10.0
    assert clusters[official.url].source_cluster_id == clusters[copy.url].source_cluster_id


def test_fetch_diagnostics_blocked_and_html_to_playwright():
    codes = classify_fetch_exception(PermissionError("403 Forbidden captcha"))
    assert "BLOCKED" in codes

    def html_short(url: str) -> RawItem:
        return _raw(url, "t", "short", published_at="2026-01-01T00:00:00+08:00")

    def pw_ok(url: str) -> RawItem:
        return _raw(url, "t", "playwright body " * 20, published_at="2026-01-01T00:00:00+08:00")

    result = fetch_with_fallback(
        "https://example.com/spa",
        html_fetcher=html_short,
        playwright_fetcher=pw_ok,
    )
    assert result.ok
    assert result.method == "playwright"
    assert "HTML_TOO_SHORT" in result.reason_codes or "JS_REQUIRED" in result.reason_codes


def test_queue_approve_does_not_verify_claim(tmp_path: Path):
    url = "https://example.com/story"
    body = "公司宣布扩大智能柜投放，正文足够用于研究验证。"
    atoms_path = tmp_path / "atoms.json"
    pipe = DiscoveryPipeline(
        provider=FakeSearchProvider([_candidate(url)]),
        pool=CandidatePool(tmp_path / "pool.json"),
        review_queue=ResearchReviewQueue(tmp_path / "queue.json"),
        atom_store=ResearchAtomStore(atoms_path),
        fetcher=lambda u: _raw(u, "t", body, published_at="2026-08-01T00:00:00+08:00"),
        config=DiscoveryPipelineConfig(
            persist=True,
            pool_path=str(tmp_path / "pool.json"),
            queue_path=str(tmp_path / "queue.json"),
            atoms_path=str(atoms_path),
        ),
    )
    record = pipe.run("智能柜", limit=1)[0]
    assert record.status is CandidateStatus.VERIFIED
    queue = ResearchReviewQueue.load_or_create(tmp_path / "queue.json")
    item = queue.get_by_candidate(record.candidate_id)
    assert item is not None
    queue.set_status(item.queue_item_id, ReviewStatus.APPROVED, reason="worth review")
    store = ResearchAtomStore.load_or_create(atoms_path)
    claim = store.get_claim(record.claim_ids[0])
    assert claim is not None
    assert claim.status is ClaimStatus.DRAFT


def test_claim_verify_preconditions_and_audit(tmp_path: Path):
    atoms = news_to_research_atoms(
        {
            "title": "测试",
            "url": "https://example.com/ok",
            "source_name": "Example",
            "published_at": "2026-08-01",
            "excerpt": "足够长的正文作为证据支撑。",
            "discovery_provider": "fake",
            "discovery_query": "智能柜",
            "discovery_candidate_id": "cand-1",
        }
    )
    store = ResearchAtomStore(tmp_path / "atoms.json")
    store.upsert_atoms(
        source=atoms.source,
        evidence=atoms.evidence,
        claims=atoms.claims,
        lineage={"intake": "discovery", "candidate_id": "cand-1"},
    )
    log_path = tmp_path / "log.jsonl"

    try:
        set_claim_status(
            store,
            atoms.claims[0].id,
            ClaimStatus.VERIFIED,
            reviewer=None,
            persist=False,
        )
        raise AssertionError("expected reviewer required")
    except ClaimReviewError as exc:
        assert exc.code == "REVIEWER_REQUIRED"

    # Snippet-only blocked
    snippet_atoms = news_to_research_atoms(
        {
            "title": "snip",
            "url": "https://example.com/snip",
            "source_name": "x",
            "excerpt": "provider generated",
        }
    )
    snippet_atoms.source.source_type = "search_snippet"
    store.upsert_atoms(
        source=snippet_atoms.source,
        evidence=snippet_atoms.evidence,
        claims=snippet_atoms.claims,
    )
    try:
        set_claim_status(
            store,
            snippet_atoms.claims[0].id,
            ClaimStatus.VERIFIED,
            reviewer="alice",
            persist=False,
        )
        raise AssertionError("snippet should fail")
    except ClaimReviewError as exc:
        assert exc.code == "CLAIM_VERIFY_PRECONDITION_FAILED"

    verified = set_claim_status(
        store,
        atoms.claims[0].id,
        ClaimStatus.VERIFIED,
        reviewer="alice",
        reason="evidence sufficient",
        log_path=log_path,
        persist=True,
    )
    assert verified.status is ClaimStatus.VERIFIED
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert "alice" in lines[0]

    # Rerun upsert must not overwrite VERIFIED
    again = news_to_research_atoms(
        {
            "title": "测试",
            "url": "https://example.com/ok",
            "source_name": "Example",
            "published_at": "2026-08-01",
            "excerpt": "足够长的正文作为证据支撑。",
        }
    )
    store.upsert_atoms(source=again.source, evidence=again.evidence, claims=again.claims)
    assert store.get_claim(atoms.claims[0].id).status is ClaimStatus.VERIFIED

    rejected = set_claim_status(
        store,
        atoms.claims[0].id,
        ClaimStatus.REJECTED,
        reviewer="bob",
        reason="revisit",
        log_path=log_path,
        persist=True,
    )
    assert rejected.status is ClaimStatus.REJECTED
    assert len(log_path.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_export_verified_only(tmp_path: Path):
    store = ResearchAtomStore(tmp_path / "atoms.json")
    good = news_to_research_atoms(
        {
            "title": "A",
            "url": "https://example.com/a",
            "source_name": "A",
            "excerpt": "正文A足够长。",
            "discovery_provider": "anysearch",
            "discovery_query": "智能柜",
        }
    )
    draft = news_to_research_atoms(
        {
            "title": "B",
            "url": "https://registry.example.com/b",
            "source_name": "Registry",
            "excerpt": "正文B足够长。",
        }
    )
    store.upsert_atoms(
        source=good.source,
        evidence=good.evidence,
        claims=good.claims,
        lineage={"intake": "discovery"},
    )
    store.upsert_atoms(
        source=draft.source,
        evidence=draft.evidence,
        claims=draft.claims,
        lineage={"intake": "registry"},
    )
    set_claim_status(
        store,
        good.claims[0].id,
        ClaimStatus.VERIFIED,
        reviewer="carol",
        reason="ok",
        log_path=tmp_path / "log.jsonl",
        persist=True,
    )
    out = tmp_path / "verified.json"
    payload = export_verified_research(store=store, output_path=out)
    assert payload["count"] == 1
    assert payload["claims"][0]["claim_id"] == good.claims[0].id
    assert draft.claims[0].id not in {c["claim_id"] for c in payload["claims"]}
    assert "snippet" not in str(payload).lower() or "provider_content" not in str(payload)


def test_batch_registry_budget():
    registry = {
        "max_queries_per_run": 3,
        "defaults": {"intent": "research"},
        "topics": {
            "smart-cabinet": {"label": "智能柜", "queries": ["智能柜", "智能货柜", "无人零售", "x"]},
            "retail-ai": {"label": "零售AI", "queries": ["零售 AI", "视觉识别"]},
        },
    }
    plan = resolve_batch_topics(topic_keys=["smart-cabinet", "retail-ai"], registry=registry)
    assert plan.mode == "batch"
    assert len(plan.queries) == 3
