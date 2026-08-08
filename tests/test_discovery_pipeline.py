"""Tests for AnySearch Discovery → Fetch → Research Verify pipeline."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from crawlers.base import RawItem
from discovery.dedupe import dedupe_candidates
from discovery.fetch import FetchResult, content_is_sufficient, fetch_with_fallback
from discovery.models import CandidateStatus, SearchCandidate, make_candidate_id
from discovery.pipeline import DiscoveryPipeline, DiscoveryPipelineConfig
from discovery.pool import CandidatePool
from discovery.providers.base import SearchProvider
from discovery.queries import resolve_queries
from publishing.editorial_gate import EditorialGateErrorCode, run_daily_editorial_gate
from research.intake import news_to_research_atoms
from research.models import ClaimStatus
from research.validators import has_blocking_issues, validate_claims, validate_discovery_atoms
from utils.helpers import generate_id, now_iso


class FakeSearchProvider(SearchProvider):
    name = "fake"

    def __init__(self, candidates: list[SearchCandidate] | dict[str, list[SearchCandidate]]):
        if isinstance(candidates, dict):
            self._by_query = candidates
            self._candidates = []
        else:
            self._by_query = None
            self._candidates = candidates

    def search(self, query: str, *, limit: int = 10, **_kwargs) -> list[SearchCandidate]:
        if self._by_query is not None:
            return list(self._by_query.get(query, []))[:limit]
        return list(self._candidates)[:limit]


def _candidate(
    *,
    url: str,
    title: str = "智能柜投放扩大",
    snippet: str = "摘要：某公司扩大智能柜投放。",
    provider_content: str = "provider 生成的不可作证据正文",
    query: str = "智能柜",
    rank: int = 1,
) -> SearchCandidate:
    return SearchCandidate(
        provider="fake",
        query=query,
        title=title,
        url=url,
        snippet=snippet,
        provider_content=provider_content,
        rank=rank,
        discovered_at="2026-08-08T10:00:00+08:00",
        language="zh-CN",
        evidence_eligible=False,
    )


def _raw_item(*, url: str, title: str, content_text: str, source: str = "discovery:fake") -> RawItem:
    return RawItem(
        id=generate_id(source, url),
        source=source,
        source_type="web",
        language="zh-CN",
        title=title,
        url=url,
        published_at="2026-08-08T09:00:00+08:00",
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


def _pipeline(provider, fetcher, tmp_path: Path | None = None, **cfg):
    pool_path = str((tmp_path or Path(".")) / "pool.json") if tmp_path else "data/state/_test_pool.json"
    config = DiscoveryPipelineConfig(persist=False, pool_path=pool_path, **cfg)
    return DiscoveryPipeline(
        provider=provider,
        pool=CandidatePool(pool_path),
        fetcher=fetcher,
        config=config,
    )


def test_snippet_only_cannot_be_verified_as_evidence(tmp_path):
    cand = _candidate(url="https://example.com/a")
    pipeline = _pipeline(
        FakeSearchProvider([cand]),
        fetcher=lambda _url: (_ for _ in ()).throw(AssertionError("must not fetch")),
        tmp_path=tmp_path,
        fetch=False,
        verify=True,
    )
    results = pipeline.run(query="智能柜", limit=1)
    assert results[0].status == CandidateStatus.DISCOVERED
    assert results[0].raw_item_id is None
    assert results[0].source_document_id is None


def test_candidate_fetch_research_verified_keeps_claim_draft(tmp_path):
    url = "https://example.com/feng-e-expand"
    cand = _candidate(url=url, title="丰e足食扩大办公楼智能柜投放")
    body = "公司宣布将在华东办公楼场景扩大智能柜投放。"

    def ok_fetch(target: str) -> RawItem:
        assert target == url
        return _raw_item(url=url, title=cand.title, content_text=body)

    pipeline = _pipeline(FakeSearchProvider([cand]), ok_fetch, tmp_path=tmp_path)
    results = pipeline.run(query="智能柜", limit=1)
    record = results[0]
    assert record.status == CandidateStatus.VERIFIED
    assert record.raw_item_id
    assert record.source_document_id
    assert record.evidence_ids
    assert record.claim_ids
    assert record.lineage["candidate_id"] == record.candidate_id
    assert all(status == ClaimStatus.DRAFT.value for status in record.metadata.get("claims_status", []))
    atoms = news_to_research_atoms(
        {
            "title": cand.title,
            "url": url,
            "source_name": "example.com",
            "published_at": "2026-08-08T09:00:00+08:00",
            "excerpt": body,
            "discovery_provider": "fake",
            "discovery_query": "智能柜",
            "discovery_candidate_id": record.candidate_id,
            "discovery_original_url": url,
        }
    )
    assert atoms.source.discovery_provider == "fake"
    assert atoms.source.discovery_candidate_id == record.candidate_id
    assert all(c.status is ClaimStatus.DRAFT for c in atoms.claims)
    assert not has_blocking_issues(
        validate_discovery_atoms(atoms.claims, {atoms.source.id: atoms.source})
    )
    assert any(
        i.code == "FACT_NOT_VERIFIED"
        for i in validate_claims(atoms.claims, {atoms.source.id: atoms.source})
    )


def test_fetch_failure_marks_fetch_failed(tmp_path):
    url = "https://example.com/missing"
    pipeline = _pipeline(
        FakeSearchProvider([_candidate(url=url)]),
        fetcher=lambda _url: (_ for _ in ()).throw(ConnectionError("HTTP 404")),
        tmp_path=tmp_path,
    )
    # Raw exception path: wrap via FetchResult by raising inside custom
    def boom(_url: str):
        raise ConnectionError("HTTP 404")

    # Use FetchResult failure instead
    pipeline = _pipeline(
        FakeSearchProvider([_candidate(url=url)]),
        fetcher=lambda _u: FetchResult(
            ok=False, reason_codes=["HTML_EMPTY", "PLAYWRIGHT_FAILED", "FETCH_FAILED"]
        ),
        tmp_path=tmp_path,
    )
    results = pipeline.run(query="智能柜", limit=1)
    assert results[0].status == CandidateStatus.FETCH_FAILED
    assert "FETCH_FAILED" in results[0].reason_codes


def test_duplicate_candidates_do_not_duplicate_evidence(tmp_path):
    url = "https://example.com/same-story"
    c1 = _candidate(url=url, title="同一新闻 A", rank=1)
    c2 = replace(c1, title="同一新闻 B", rank=2, snippet="另一摘要")
    calls = {"n": 0}

    def ok_fetch(target: str) -> RawItem:
        calls["n"] += 1
        return _raw_item(url=target, title="同一新闻", content_text="正文内容足够长用于验证。")

    pipeline = _pipeline(FakeSearchProvider([c1, c2]), ok_fetch, tmp_path=tmp_path)
    results = pipeline.run(query="智能柜", limit=5)
    unique = [r for r in results if r.status == CandidateStatus.VERIFIED]
    assert len(unique) == 1
    assert calls["n"] == 1


def test_durable_pool_reuses_canonical_url(tmp_path):
    pool_path = tmp_path / "candidate_pool.json"
    url = "https://www.example.com/story"
    cand = _candidate(url=url, query="智能柜")
    body = "足够长的正文用于验证候选持久化与再次发现。"

    pipe1 = DiscoveryPipeline(
        provider=FakeSearchProvider([cand]),
        pool=CandidatePool(pool_path),
        fetcher=lambda u: _raw_item(url=u, title="t", content_text=body),
        config=DiscoveryPipelineConfig(persist=True, pool_path=str(pool_path)),
    )
    first = pipe1.run("智能柜", limit=1)[0]
    assert first.status == CandidateStatus.VERIFIED
    assert pool_path.exists()

    pipe2 = DiscoveryPipeline(
        provider=FakeSearchProvider([_candidate(url=url, query="无人零售", title="再次发现")]),
        pool=CandidatePool.load_or_create(pool_path),
        fetcher=lambda _u: (_ for _ in ()).throw(AssertionError("must not refetch")),
        config=DiscoveryPipelineConfig(persist=True, pool_path=str(pool_path)),
    )
    second = pipe2.run("无人零售", limit=1)[0]
    assert second.candidate_id == first.candidate_id
    assert second.status == CandidateStatus.VERIFIED
    assert second.candidate.query == "无人零售"
    assert "智能柜" in (second.metadata.get("prior_queries") or [])


def test_dedupe_canonicalizes_tracking_params():
    a = _candidate(url="https://example.com/x?utm_source=as&id=1")
    b = _candidate(url="https://example.com/x?id=1", rank=2)
    out = dedupe_candidates([a, b])
    assert len(out) == 1
    assert "utm_source" not in out[0].url
    assert out[0].url.startswith("https://example.com/x")


def test_dedupe_preserves_www_for_fetch():
    a = _candidate(url="https://www.ieou.com/blog/20230214?utm_source=x")
    out = dedupe_candidates([a])
    assert out[0].url.startswith("https://www.ieou.com/blog/20230214")
    assert "utm_source" not in out[0].url


def test_registry_and_discovery_share_research_validators():
    for item in (
        {
            "title": "友宝发布智能柜报告",
            "url": "https://registry.example.com/youbao",
            "source_name": "registry-source",
            "published_at": "2026-08-01",
            "excerpt": "友宝披露智能柜运营数据更新。",
        },
        {
            "title": "无人零售终端扩张",
            "url": "https://discovery.example.com/expand",
            "source_name": "discovery-source",
            "published_at": "2026-08-02",
            "excerpt": "多家运营商扩大无人零售终端投放。",
            "discovery_provider": "anysearch",
            "discovery_query": "无人零售",
            "discovery_candidate_id": "cand-test",
        },
    ):
        atoms = news_to_research_atoms(item)
        assert not has_blocking_issues(
            validate_discovery_atoms(atoms.claims, {atoms.source.id: atoms.source})
        )


def test_empty_fetched_body_rejected(tmp_path):
    url = "https://example.com/empty"
    pipeline = _pipeline(
        FakeSearchProvider([_candidate(url=url)]),
        fetcher=lambda u: FetchResult(
            item=_raw_item(url=u, title="空页", content_text="   "),
            method="html",
            ok=True,
        ),
        tmp_path=tmp_path,
    )
    results = pipeline.run(query="智能柜", limit=1)
    assert results[0].status == CandidateStatus.REJECTED
    assert "SOURCE_CONTENT_EMPTY" in results[0].reason_codes


def test_publishing_gate_hard_fails_search_snippet_evidence():
    data = {
        "title": "仅靠搜索摘要的错误日报",
        "date": "2026-08-08",
        "sections": [
            {
                "level": "core",
                "title": "摘要冒充证据",
                "excerpt": "某公司扩大智能柜投放。",
                "source_url": "https://example.com/real-page",
                "source_name": "AnySearch snippet",
                "source_type": "search_snippet",
            }
        ],
    }
    result = run_daily_editorial_gate(data)
    assert not result.passed
    assert result.has_error(EditorialGateErrorCode.SEARCH_SNIPPET_AS_EVIDENCE)


def test_anysearch_provider_parses_markdown_search_results():
    from discovery.providers.anysearch import _parse_markdown_results

    text = (
        "## Search Results (2 results, 10ms)\n\n"
        "### 1. 智能柜简介\n"
        "- **URL**: https://example.com/a\n"
        "- 这是摘要一行。\n\n"
        "### 2. 无人零售\n"
        "- **URL**: https://example.com/b\n"
        "- 第二段摘要。\n"
    )
    rows = _parse_markdown_results(text)
    assert len(rows) == 2
    assert rows[0]["url"] == "https://example.com/a"


def test_anysearch_provider_parses_mock_http_payload_without_network(monkeypatch):
    from discovery.providers import anysearch as anysearch_mod

    captured = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                '[{"title":"T1","url":"https://example.com/1",'
                                '"snippet":"s1","content":"pc1"}]'
                            ),
                        }
                    ]
                },
            }

        def raise_for_status(self):
            return None

    class FakeSession:
        def post(self, url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers or {}
            captured["json"] = json
            return FakeResp()

    monkeypatch.setenv("ANYSEARCH_API_KEY", "as_sk_test_key")
    provider = anysearch_mod.AnySearchProvider(session=FakeSession())
    hits = provider.search("智能柜", limit=3)
    assert len(hits) == 1
    assert hits[0].evidence_eligible is False
    assert captured["json"]["params"]["name"] == "search"


def test_query_registry_topic_and_company():
    registry = {
        "max_queries_per_run": 3,
        "topics": {
            "smart-cabinet": {
                "label": "智能柜",
                "queries": ["智能柜", "智能货柜", "无人零售", "自动售货机"],
            }
        },
        "company_query_templates": [
            "{company} 智能柜",
            "{company} 无人零售",
            "{company} 自动售货",
            "{company} AI",
        ],
    }
    topic = resolve_queries(topic="smart-cabinet", registry=registry)
    assert topic.mode == "topic"
    assert topic.queries == ["智能柜", "智能货柜", "无人零售"]
    company = resolve_queries(company="友宝", registry=registry)
    assert company.queries == ["友宝 智能柜", "友宝 无人零售", "友宝 自动售货"]
    assert len(company.queries) == 3
    direct = resolve_queries(query="智能柜", registry=registry)
    assert direct.queries == ["智能柜"]


def test_html_success_skips_playwright():
    calls = {"html": 0, "pw": 0}

    def html_ok(url: str) -> RawItem:
        calls["html"] += 1
        return _raw_item(url=url, title="ok", content_text="x" * 120)

    def pw_should_not(url: str) -> RawItem:
        calls["pw"] += 1
        raise AssertionError("playwright should not run")

    result = fetch_with_fallback(
        "https://example.com/ok",
        html_fetcher=html_ok,
        playwright_fetcher=pw_should_not,
    )
    assert result.ok
    assert result.method == "html"
    assert calls == {"html": 1, "pw": 0}


def test_html_empty_playwright_success():
    def html_empty(url: str) -> RawItem:
        return _raw_item(url=url, title="empty", content_text="")

    def pw_ok(url: str) -> RawItem:
        return _raw_item(url=url, title="pw", content_text="playwright body " * 10)

    result = fetch_with_fallback(
        "https://example.com/spa",
        html_fetcher=html_empty,
        playwright_fetcher=pw_ok,
    )
    assert result.ok
    assert result.method == "playwright"
    assert "HTML_EMPTY" in result.reason_codes


def test_html_empty_playwright_fail():
    def html_empty(url: str) -> RawItem:
        raise ConnectionError("html fail")

    def pw_fail(url: str) -> RawItem:
        raise ConnectionError("pw fail")

    result = fetch_with_fallback(
        "https://example.com/dead",
        html_fetcher=html_empty,
        playwright_fetcher=pw_fail,
    )
    assert not result.ok
    assert "HTML_EMPTY" in result.reason_codes
    assert "PLAYWRIGHT_FAILED" in result.reason_codes
    assert "FETCH_FAILED" in result.reason_codes


def test_pipeline_uses_playwright_fallback_fetch_result(tmp_path):
    url = "https://example.com/spa-article"
    pipeline = _pipeline(
        FakeSearchProvider([_candidate(url=url)]),
        fetcher=lambda u: FetchResult(
            item=_raw_item(url=u, title="spa", content_text="从 Playwright 拿到的有效正文内容。"),
            method="playwright",
            reason_codes=["HTML_EMPTY"],
            ok=True,
        ),
        tmp_path=tmp_path,
    )
    record = pipeline.run("智能柜", limit=1)[0]
    assert record.status == CandidateStatus.VERIFIED
    assert record.fetch_method == "playwright"


def test_content_is_sufficient_threshold():
    assert not content_is_sufficient("short")
    assert content_is_sufficient("x" * 80)


def test_make_candidate_id_stable_across_queries():
    a = make_candidate_id("fake", "https://example.com/a")
    b = make_candidate_id("fake", "https://example.com/a")
    assert a == b
    assert a.startswith("cand-")
