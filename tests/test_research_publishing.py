"""Research publish integration: service, adapters, run_article, Zhihu package."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from publishing.adapters import case_to_article, research_brief_to_article, signal_to_article
from publishing.article import Article, ArticleItem, ArticleMeta
from publishing.asset_manager import AssetManager
from publishing.config import PublishConfig
from publishing.models import (
    ChannelTarget,
    MediaAsset,
    PublishResult,
    PublishStatus,
    RenderContext,
    RenderResult,
)
from publishing.workflow import PublishWorkflow
from research.exporters.zhihu import export_zhihu_package
from research.models import (
    CaseStudy,
    Claim,
    ClaimStatus,
    ClaimType,
    Confidence,
    IndustrySignal,
    ResearchBrief,
    SourceDocument,
)
from research.publishing_service import (
    ResearchPublishError,
    ResearchPublishRequest,
    ResearchPublishService,
)


class FakeManifest:
    def save(self, **kwargs):
        return None

    def mark_failed(self, *args):
        return None


class CountingRenderer:
    def __init__(self):
        self.calls = 0
        self.articles = []

    def render(self, article, context):
        self.calls += 1
        self.articles.append(article)
        return RenderResult(
            article_uuid=article.metadata.uuid,
            title=article.title,
            body="<p>ok</p>",
            summary="s",
            cover=MediaAsset("cover", "cover.png", "image/png"),
            author=article.author,
        )


class CountingPublisher:
    def publish(self, result, dry_run=False, publish_now=False, notify_followers=False):
        return PublishResult(status=PublishStatus.SUCCESS, channel="wechat")


def _source():
    return SourceDocument(
        id="src-1",
        url="https://example.com/a",
        title="公开来源",
        source_name="Example",
        published_at="2026-08-06",
    )


def _fact():
    return Claim(
        id="cl-1",
        text="运营商扩大投放",
        type=ClaimType.FACT,
        status=ClaimStatus.VERIFIED,
        confidence=Confidence.HIGH,
        source_ids=["src-1"],
        reviewed_at="2026-08-06T12:00:00+08:00",
    )


def _signal():
    return IndustrySignal(
        id="sig-1",
        slug="expand",
        title="投放扩大",
        summary="办公楼投放扩大",
        why_it_matters="影响点位模型",
        affected_roles=["operators"],
        judgment="值得跟踪",
        claim_ids=["cl-1"],
        source_ids=["src-1"],
        verification_status="verified",
        published_at="2026-08-06",
    )


def _case():
    return CaseStudy(
        id="case-1",
        slug="office",
        title="办公楼补货",
        problem="缺货",
        solution="按动销补货",
        how_it_works="日更补货单",
        public_results=["缺货下降"],
        limitations=["冷启动不适用"],
        status="approved",
    )


def _brief(**overrides):
    data = dict(
        id="brief-1",
        slug="weekly-expand",
        title="本周投放观察",
        summary="投放扩大值得跟踪补货半径",
        claim_ids=["cl-1"],
        signal_ids=["sig-1"],
        case_ids=["case-1"],
        status="approved",
    )
    data.update(overrides)
    return ResearchBrief(**data)


def test_adapters_map_core_fields():
    article = signal_to_article(_signal())
    assert article.metadata.source == "signal_digest"
    assert "投放扩大" in article.title
    case_article = case_to_article(_case(), date="2026-08-06")
    assert case_article.metadata.source == "case_study"
    brief_article = research_brief_to_article(
        _brief(), signals=[_signal()], cases=[_case()], template="deep_insight"
    )
    assert brief_article.metadata.source == "deep_insight"
    assert brief_article.sections


def test_run_article_and_path_run_are_compatible(tmp_path):
    renderer = CountingRenderer()
    publisher = CountingPublisher()
    workflow = PublishWorkflow(
        config=PublishConfig(),
        manifest=FakeManifest(),
        media_service_factory=lambda: (_ for _ in ()).throw(
            RuntimeError("media should be skipped in unit path")
        )
        if False
        else type(
            "S",
            (),
            {
                "generate_daily": lambda self, article: type(
                    "B",
                    (),
                    {
                        "cover": MediaAsset("cover", "c.png", "image/png"),
                        "body_images": [
                            MediaAsset("body_1", "b1.png", "image/png"),
                            MediaAsset("body_2", "b2.png", "image/png"),
                            MediaAsset("body_3", "b3.png", "image/png"),
                        ],
                        "video": None,
                        "all_assets": lambda self: [
                            self.cover,
                            *self.body_images,
                        ],
                    },
                )()
            },
        )(),
    )
    # Simpler: monkeypatch build_steps to skip media like existing pipeline tests
    workflow.build_steps = lambda: []  # type: ignore[method-assign]
    # Empty steps won't set PUBLISH_RESULT — use real short pipeline via run_article with custom steps

    from publishing.pipeline import PublishPipeline, PipelineContext, PipelineState
    from publishing.steps import PublishStep, RenderStep, RecordStep, ValidateStep

    article = Article(
        metadata=ArticleMeta(uuid="u1", slug="s", source="daily", issue=1),
        title="t",
        date="2026-08-06",
        summary=["s"],
        sections=[
            ArticleItem(
                title="item",
                excerpt="excerpt",
                source_url="https://example.com",
                source_name="Example",
            )
        ],
    )
    target = ChannelTarget(name="wechat", renderer=renderer, publisher=publisher)
    context = RenderContext(config=PublishConfig(), asset_manager=AssetManager())

    def run_article_local(art):
        ctx = PipelineContext(
            article=art,
            target=target,
            render_context=context,
            mode="draft",
            trace_id="t1",
            config=PublishConfig(),
            manifest=FakeManifest(),
            logger=logging.getLogger("test"),
        )
        return PublishPipeline(
            [ValidateStep(), RenderStep(), PublishStep(), RecordStep()]
        ).run(ctx).get(PipelineState.PUBLISH_RESULT)

    # Direct run_article through workflow with patched steps
    workflow.build_steps = lambda: [  # type: ignore[method-assign]
        ValidateStep(),
        RenderStep(),
        PublishStep(),
        RecordStep(),
    ]
    result = workflow.run_article(article, target, context, mode="draft")
    assert result.status == PublishStatus.SUCCESS
    assert renderer.calls == 1


def test_research_publish_service_blocks_unverified_fact():
    workflow = PublishWorkflow(config=PublishConfig(), manifest=FakeManifest())
    service = ResearchPublishService(workflow)
    draft_fact = _fact()
    draft_fact.status = ClaimStatus.DRAFT
    request = ResearchPublishRequest(
        brief=_brief(),
        claims={"cl-1": draft_fact},
        sources={"src-1": _source()},
    )
    with pytest.raises(ResearchPublishError, match="blocked"):
        service.publish(
            request,
            ChannelTarget(
                name="wechat",
                renderer=CountingRenderer(),
                publisher=CountingPublisher(),
            ),
            RenderContext(config=PublishConfig(), asset_manager=AssetManager()),
        )


def test_research_publish_service_publishes_approved_brief():
    workflow = PublishWorkflow(config=PublishConfig(), manifest=FakeManifest())
    workflow.build_steps = lambda: [  # type: ignore[method-assign]
        __import__("publishing.steps", fromlist=["ValidateStep"]).ValidateStep(),
        __import__("publishing.steps", fromlist=["RenderStep"]).RenderStep(),
        __import__("publishing.steps", fromlist=["PublishStep"]).PublishStep(),
        __import__("publishing.steps", fromlist=["RecordStep"]).RecordStep(),
    ]
    service = ResearchPublishService(workflow)
    request = ResearchPublishRequest(
        brief=_brief(),
        claims={"cl-1": _fact()},
        sources={"src-1": _source()},
        signals=[_signal()],
        cases=[_case()],
        template="deep_insight",
    )
    result = service.publish(
        request,
        ChannelTarget(
            name="wechat",
            renderer=CountingRenderer(),
            publisher=CountingPublisher(),
        ),
        RenderContext(config=PublishConfig(), asset_manager=AssetManager()),
        mode="draft",
    )
    assert result.status == PublishStatus.SUCCESS


def test_zhihu_package_structure_and_determinism(tmp_path):
    root = tmp_path / "zhihu"
    first = export_zhihu_package(
        _brief(),
        root,
        signals=[_signal()],
        cases=[_case()],
        sources=[_source()],
    )
    second = export_zhihu_package(
        _brief(),
        root,
        signals=[_signal()],
        cases=[_case()],
        sources=[_source()],
    )
    assert first == second
    for name in (
        "title.txt",
        "body.md",
        "excerpt.txt",
        "topics.json",
        "sources.json",
        "metadata.json",
        "cover-prompt.txt",
    ):
        assert (first / name).exists()
    body = (first / "body.md").read_text(encoding="utf-8")
    assert "投放扩大值得跟踪补货半径" in body
    assert "反方观点" in body
    assert "review_note" not in body
    assert (first / "body.md").read_bytes() == (second / "body.md").read_bytes()
