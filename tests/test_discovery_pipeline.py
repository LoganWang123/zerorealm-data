"""Tests for AnySearch Discovery → Fetch → Research Verify pipeline."""

from __future__ import annotations

from dataclasses import replace

from crawlers.base import RawItem
from discovery.dedupe import dedupe_candidates
from discovery.models import CandidateStatus, SearchCandidate
from discovery.pipeline import DiscoveryPipeline, DiscoveryPipelineConfig
from discovery.pool import CandidatePool
from discovery.providers.base import SearchProvider
from publishing.editorial_gate import EditorialGateErrorCode, run_daily_editorial_gate
from research.intake import news_to_research_atoms
from research.models import ClaimStatus
from research.validators import has_blocking_issues, validate_claims, validate_discovery_atoms
from utils.helpers import generate_id, now_iso


class FakeSearchProvider(SearchProvider):
    name = "fake"

    def __init__(self, candidates: list[SearchCandidate]):
        self._candidates = candidates

    def search(self, query: str, *, limit: int = 10, **_kwargs) -> list[SearchCandidate]:
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


def test_snippet_only_cannot_be_verified_as_evidence():
    cand = _candidate(url="https://example.com/a")
    pool = CandidatePool()
    provider = FakeSearchProvider([cand])

    def fail_fetch(_url: str):
        raise AssertionError("snippet-only path must not fetch for this assertion")

    pipeline = DiscoveryPipeline(
        provider=provider,
        pool=pool,
        fetcher=fail_fetch,
        config=DiscoveryPipelineConfig(fetch=False, verify=True),
    )
    results = pipeline.run(query="智能柜", limit=1)
    assert len(results) == 1
    assert results[0].status == CandidateStatus.DISCOVERED
    assert results[0].status != CandidateStatus.VERIFIED
    assert results[0].raw_item_id is None
    assert results[0].source_document_id is None


def test_candidate_fetch_research_verified_keeps_claim_draft():
    url = "https://example.com/feng-e-expand"
    cand = _candidate(url=url, title="丰e足食扩大办公楼智能柜投放")
    body = "公司宣布将在华东办公楼场景扩大智能柜投放。"

    def ok_fetch(target: str) -> RawItem:
        assert target == url
        return _raw_item(url=url, title=cand.title, content_text=body)

    pool = CandidatePool()
    pipeline = DiscoveryPipeline(
        provider=FakeSearchProvider([cand]),
        pool=pool,
        fetcher=ok_fetch,
    )
    results = pipeline.run(query="智能柜", limit=1)
    assert len(results) == 1
    record = results[0]
    assert record.status == CandidateStatus.VERIFIED
    assert record.raw_item_id
    assert record.source_document_id
    assert record.evidence_ids
    assert record.claim_ids
    assert record.lineage["candidate_id"] == record.candidate_id
    assert record.lineage["raw_item_id"] == record.raw_item_id
    assert record.lineage["source_document_id"] == record.source_document_id
    assert all(status == ClaimStatus.DRAFT.value for status in record.metadata.get("claims_status", []))
    # Reconstruct atoms the same way pipeline does and assert draft + validators
    atoms = news_to_research_atoms(
        {
            "title": cand.title,
            "url": url,
            "source_name": "example.com",
            "published_at": "2026-08-08T09:00:00+08:00",
            "excerpt": body,
        }
    )
    assert all(c.status is ClaimStatus.DRAFT for c in atoms.claims)
    discovery_issues = validate_discovery_atoms(atoms.claims, {atoms.source.id: atoms.source})
    assert not has_blocking_issues(discovery_issues)
    # Publish validators still require manual ClaimStatus.VERIFIED
    publish_issues = validate_claims(atoms.claims, {atoms.source.id: atoms.source})
    assert any(i.code == "FACT_NOT_VERIFIED" for i in publish_issues)


def test_fetch_failure_marks_fetch_failed():
    url = "https://example.com/missing"
    cand = _candidate(url=url)

    def boom(_url: str):
        raise ConnectionError("HTTP 404")

    pipeline = DiscoveryPipeline(
        provider=FakeSearchProvider([cand]),
        pool=CandidatePool(),
        fetcher=boom,
    )
    results = pipeline.run(query="智能柜", limit=1)
    assert results[0].status == CandidateStatus.FETCH_FAILED
    assert "SOURCE_FETCH_FAILED" in results[0].reason_codes


def test_duplicate_candidates_do_not_duplicate_evidence():
    url = "https://example.com/same-story"
    c1 = _candidate(url=url, title="同一新闻 A", rank=1)
    c2 = replace(c1, title="同一新闻 B", rank=2, snippet="另一摘要")

    calls = {"n": 0}

    def ok_fetch(target: str) -> RawItem:
        calls["n"] += 1
        return _raw_item(url=target, title="同一新闻", content_text="正文内容足够长用于验证。")

    pipeline = DiscoveryPipeline(
        provider=FakeSearchProvider([c1, c2]),
        pool=CandidatePool(),
        fetcher=ok_fetch,
    )
    results = pipeline.run(query="智能柜", limit=5)
    unique = [r for r in results if r.status == CandidateStatus.VERIFIED]
    assert len(unique) == 1
    assert calls["n"] == 1
    assert len(unique[0].evidence_ids) == 1


def test_dedupe_canonicalizes_tracking_params():
    a = _candidate(url="https://example.com/x?utm_source=as&id=1")
    b = _candidate(url="https://example.com/x?id=1", rank=2)
    out = dedupe_candidates([a, b])
    assert len(out) == 1
    assert "utm_source" not in out[0].url
    # original host/path preserved for fetch; tracking stripped via normalize for key only
    assert out[0].url.startswith("https://example.com/x")


def test_dedupe_preserves_www_for_fetch():
    a = _candidate(url="https://www.ieou.com/blog/20230214?utm_source=x")
    out = dedupe_candidates([a])
    assert len(out) == 1
    assert out[0].url.startswith("https://www.ieou.com/blog/20230214")
    assert "utm_source" not in out[0].url


def test_registry_and_discovery_share_research_validators():
    """Both intake paths produce atoms accepted by the same discovery validators."""
    registry_item = {
        "title": "友宝发布智能柜报告",
        "url": "https://registry.example.com/youbao",
        "source_name": "registry-source",
        "published_at": "2026-08-01",
        "excerpt": "友宝披露智能柜运营数据更新。",
    }
    discovery_item = {
        "title": "无人零售终端扩张",
        "url": "https://discovery.example.com/expand",
        "source_name": "discovery-source",
        "published_at": "2026-08-02",
        "excerpt": "多家运营商扩大无人零售终端投放。",
    }
    for item in (registry_item, discovery_item):
        atoms = news_to_research_atoms(item)
        issues = validate_discovery_atoms(atoms.claims, {atoms.source.id: atoms.source})
        assert not has_blocking_issues(issues)


def test_empty_fetched_body_rejected():
    url = "https://example.com/empty"
    cand = _candidate(url=url)

    def empty_fetch(target: str) -> RawItem:
        return _raw_item(url=target, title="空页", content_text="   ")

    pipeline = DiscoveryPipeline(
        provider=FakeSearchProvider([cand]),
        pool=CandidatePool(),
        fetcher=empty_fetch,
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
    assert rows[0]["title"] == "智能柜简介"
    assert "摘要" in rows[0]["snippet"]


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
    assert hits[0].url == "https://example.com/1"
    assert hits[0].snippet == "s1"
    assert hits[0].provider_content == "pc1"
    assert hits[0].evidence_eligible is False
    assert "Authorization" in captured["headers"]
    assert captured["json"]["method"] == "tools/call"
    assert captured["json"]["params"]["name"] == "search"
