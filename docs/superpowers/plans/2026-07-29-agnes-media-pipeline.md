# Agnes Media Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one Agnes-backed media generation layer that creates fixed homepage media on demand and blocks daily WeChat publication unless a generated cover, three body images, and one reusable short video are valid.

**Architecture:** `zerorealm-data` owns the provider client, prompts, asset manifest, download/validation, and generation workflow. The existing publish pipeline receives a media-generation step between content validation and rendering; the Next.js site consumes only committed/static homepage assets and never receives an Agnes key.

**Tech Stack:** Python 3.11, dataclasses, requests, pytest, Next.js 16, React 19, TypeScript, Node test runner.

## Global Constraints

- Agnes credentials come only from `AGNES_API_KEY`; secrets never appear in repo files, frontend bundles, logs, or exceptions.
- Default API base is `https://apihub.agnes-ai.com/v1`.
- Default models are `agnes-image-2.1-flash` and `agnes-video-v2.0`.
- Homepage media is generated once and overwritten only with an explicit `--force`.
- Each daily article requires 1 cover image, 3 body images, and 1 approximately 15-second 9:16 video.
- Any Agnes, download, validation, WeChat video upload, or video embed failure blocks draft creation and publication.
- Website video has controls and poster but no `autoplay`, loop, or background-video behavior.
- Preserve all unrelated dirty-worktree changes and stage/commit only files owned by each task.

---

## File Map

### `zerorealm-data`

- `publishing/config.py`: non-secret media settings.
- `publishing/models.py`: `MediaAsset` and `MediaBundle` shared pipeline values.
- `publishing/media_generation/client.py`: Agnes HTTP protocol, image response parsing, video polling.
- `publishing/media_generation/prompts.py`: deterministic homepage and daily prompt construction.
- `publishing/media_generation/manifest.py`: atomic JSON manifest read/write and reuse checks.
- `publishing/media_generation/service.py`: orchestrates requested assets, downloads, hashes, and partial resume.
- `publishing/media_generation/validation.py`: validates file type, dimensions, duration metadata, and hashes.
- `publishing/media_generation/homepage.py`: manual homepage generation and safe copy into the website.
- `publishing/steps.py`, `publishing/pipeline.py`, `publishing/workflow.py`: daily pipeline integration.
- `publishing/wechat/renderer.py`, `publishing/wechat/client.py`, `publishing/wechat/publisher.py`: body-image and video channel handling.
- `generate_media.py`: CLI.
- `config/publish.yaml`: documented defaults.
- `tests/test_agnes_client.py`, `tests/test_media_generation.py`, `tests/test_media_pipeline.py`, `tests/test_wechat_media.py`: Python behavior tests.

### `zerorealm-website`

- `lib/home-media.ts`: typed static-manifest loader.
- `components/home/HomeMedia.tsx`: accessible image/video presentation.
- `components/home/Hero.tsx`: integrates the generated hero image.
- `app/page.tsx`: inserts the video showcase.
- `public/media/home/README.md`: asset contract without generated binaries.
- `tests/home-media.test.ts`: manifest and markup contract tests.

---

### Task 1: Media configuration and domain types

**Files:**
- Modify: `zerorealm-data/publishing/config.py`
- Modify: `zerorealm-data/publishing/models.py`
- Modify: `zerorealm-data/config/publish.yaml`
- Test: `zerorealm-data/tests/test_media_generation.py`

**Interfaces:**
- Produces: `MediaConfig`, `MediaAsset`, `MediaBundle`.
- Consumes: existing `PublishConfig.load()` YAML merge.

- [ ] **Step 1: Write the failing configuration and model tests**

```python
from publishing.config import PublishConfig
from publishing.models import MediaAsset, MediaBundle


def test_publish_config_loads_agnes_media_defaults(tmp_path):
    path = tmp_path / "publish.yaml"
    path.write_text(
        "media:\n"
        "  enabled: true\n"
        "  provider: agnes\n"
        "  body_image_count: 3\n"
        "  video_duration_seconds: 15\n",
        encoding="utf-8",
    )
    config = PublishConfig.load(str(path))
    assert config.media.enabled is True
    assert config.media.provider == "agnes"
    assert config.media.body_image_count == 3
    assert config.media.video_duration_seconds == 15


def test_media_bundle_requires_named_cover_body_images_and_video():
    cover = MediaAsset(role="cover", local_path="cover.png", mime="image/png")
    body = [
        MediaAsset(role=f"body_{index}", local_path=f"body-{index}.png", mime="image/png")
        for index in range(1, 4)
    ]
    video = MediaAsset(role="short_video", local_path="short.mp4", mime="video/mp4")
    bundle = MediaBundle(cover=cover, body_images=body, video=video)
    assert bundle.all_assets() == [cover, *body, video]
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
pytest tests/test_media_generation.py -q
```

Expected: import failure for the missing `MediaConfig`, `MediaAsset`, or `MediaBundle`.

- [ ] **Step 3: Add minimal dataclasses and config parsing**

Implement:

```python
@dataclass
class MediaConfig:
    enabled: bool = True
    provider: str = "agnes"
    image_model: str = "agnes-image-2.1-flash"
    video_model: str = "agnes-video-v2.0"
    body_image_count: int = 3
    video_duration_seconds: int = 15
    video_aspect_ratio: str = "9:16"
    poll_interval_seconds: int = 5
    poll_timeout_seconds: int = 600
    reuse_existing: bool = True


@dataclass
class MediaAsset:
    role: str
    local_path: str
    mime: str
    width: int = 0
    height: int = 0
    duration_seconds: float = 0.0
    sha256: str = ""
    prompt_version: str = "v1"
    model: str = ""
    remote_url: str = ""
    media_id: str = ""


@dataclass
class MediaBundle:
    cover: MediaAsset
    body_images: list[MediaAsset]
    video: MediaAsset

    def all_assets(self) -> list[MediaAsset]:
        return [self.cover, *self.body_images, self.video]
```

Add `media: MediaConfig` to `PublishConfig` and parse `data["media"]`.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
pytest tests/test_media_generation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit only Task 1 files**

```powershell
git add publishing/config.py publishing/models.py config/publish.yaml tests/test_media_generation.py
git commit -m "feat: add media generation configuration"
```

### Task 2: Agnes API client

**Files:**
- Create: `zerorealm-data/publishing/media_generation/__init__.py`
- Create: `zerorealm-data/publishing/media_generation/client.py`
- Test: `zerorealm-data/tests/test_agnes_client.py`

**Interfaces:**
- Produces: `AgnesClient.generate_image(prompt, size) -> bytes`.
- Produces: `AgnesClient.generate_video(prompt, aspect_ratio, duration_seconds) -> bytes`.
- Produces: `AgnesAPIError(retryable: bool)`.
- Consumes: injected `requests.Session`, environment configuration, injected clock/sleeper for deterministic polling.

- [ ] **Step 1: Read the test-quality rules before adding tests**

Run:

```powershell
Get-Content -Raw "C:\Users\wang'long\.codex\skills\test-driven-development\writing-good-tests.md"
```

- [ ] **Step 2: Write failing tests for URL and Base64 image responses**

Use a small fake session whose `post()` returns:

```python
{"data": [{"b64_json": base64.b64encode(b"png-bytes").decode()}]}
```

and assert:

```python
assert client.generate_image("prompt", "900x383") == b"png-bytes"
assert fake_session.last_headers["Authorization"] == "Bearer test-key"
assert fake_session.last_json["model"] == "agnes-image-2.1-flash"
```

Add a URL-response test where `data[0].url` is downloaded through the same session.

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```powershell
pytest tests/test_agnes_client.py -q
```

Expected: module import failure.

- [ ] **Step 4: Implement image generation with explicit response parsing**

Implement `AgnesClient` with:

```python
class AgnesClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://apihub.agnes-ai.com/v1",
        image_model: str = "agnes-image-2.1-flash",
        video_model: str = "agnes-video-v2.0",
        session: requests.Session | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        if not api_key:
            raise ValueError("AGNES_API_KEY is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._image_model = image_model
        self._video_model = video_model
        self._session = session or requests.Session()
        self._sleeper = sleeper
        self._monotonic = monotonic
```

Never include the API key or raw Authorization header in exception messages.

- [ ] **Step 5: Add failing async-video tests**

Cover:

- create response with `video_id`;
- polling from `queued` to `completed`;
- output URL download;
- `failed` status;
- poll timeout;
- 401 non-retryable and 429/5xx retryable error classification.

Expected API:

```python
video = client.generate_video(
    prompt="vertical retail intelligence animation",
    aspect_ratio="9:16",
    duration_seconds=15,
    poll_interval_seconds=0,
    poll_timeout_seconds=30,
)
assert video == b"mp4-bytes"
```

- [ ] **Step 6: Run video tests and verify RED**

Run:

```powershell
pytest tests/test_agnes_client.py -q
```

Expected: failures because video methods are absent.

- [ ] **Step 7: Implement bounded video creation and polling**

Create video with `POST {base_url}/videos`. Extract IDs in the order
`video_id`, `id`, `task_id`. Build the poll URL from
`AGNES_VIDEO_STATUS_URL_TEMPLATE`, defaulting to:

```text
https://apihub.agnes-ai.com/agnesapi?video_id={video_id}
```

Parse status and output through small pure helpers so response variants are unit-tested.

- [ ] **Step 8: Run focused and full Python tests**

Run:

```powershell
pytest tests/test_agnes_client.py -q
pytest -q
```

Expected: PASS.

- [ ] **Step 9: Commit only Task 2 files**

```powershell
git add publishing/media_generation/__init__.py publishing/media_generation/client.py tests/test_agnes_client.py
git commit -m "feat: add Agnes image and video client"
```

### Task 3: Prompt builder, manifest, generation service, and validation

**Files:**
- Create: `zerorealm-data/publishing/media_generation/prompts.py`
- Create: `zerorealm-data/publishing/media_generation/manifest.py`
- Create: `zerorealm-data/publishing/media_generation/service.py`
- Create: `zerorealm-data/publishing/media_generation/validation.py`
- Modify: `zerorealm-data/tests/test_media_generation.py`

**Interfaces:**
- Produces: `PromptSet(cover, body_images, video, version)`.
- Produces: `MediaGenerationService.generate_daily(article) -> MediaBundle`.
- Produces: `MediaValidator.validate(bundle) -> list[str]`.
- Consumes: `AgnesClient`, `Article`, `MediaConfig`, filesystem path.

- [ ] **Step 1: Write failing prompt and manifest-reuse tests**

Assert that prompts include the article title/summary, ZeroRealm visual constraints, required role, no unsupported text rendering, and stable `prompt_version`.

Create a temp manifest and assert:

```python
first = service.generate_daily(article)
second = service.generate_daily(article)
assert second == first
assert fake_client.image_calls == 4
assert fake_client.video_calls == 1
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
pytest tests/test_media_generation.py -q
```

- [ ] **Step 3: Implement deterministic prompts and atomic manifest writes**

Write manifest to a sibling temporary file and replace only after all recorded fields are durable:

```python
temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
temp_path.replace(manifest_path)
```

Reuse requires matching:

- article UUID;
- content revision;
- prompt version;
- model;
- file existence;
- SHA-256.

- [ ] **Step 4: Add failing partial-resume and invalid-media tests**

Test that a missing `body_2` is regenerated without regenerating the other four assets.
Test zero bytes, wrong magic header, wrong dimensions, wrong video aspect ratio, and wrong hash.

- [ ] **Step 5: Run tests and verify RED**

Run:

```powershell
pytest tests/test_media_generation.py -q
```

- [ ] **Step 6: Implement generation, atomic file writes, hashes, and validation**

Write each download to `*.partial`, validate non-empty content, then replace its destination.
Keep media probing behind an injected `probe(path) -> MediaProbe` function so unit tests do not require external binaries.

- [ ] **Step 7: Run focused and full tests**

Run:

```powershell
pytest tests/test_media_generation.py -q
pytest -q
```

- [ ] **Step 8: Commit only Task 3 files**

```powershell
git add publishing/media_generation tests/test_media_generation.py
git commit -m "feat: generate and validate Agnes media bundles"
```

### Task 4: Add blocking media steps to the publish pipeline

**Files:**
- Modify: `zerorealm-data/publishing/pipeline.py`
- Modify: `zerorealm-data/publishing/steps.py`
- Modify: `zerorealm-data/publishing/workflow.py`
- Modify: `zerorealm-data/publishing/factory.py`
- Test: `zerorealm-data/tests/test_media_pipeline.py`

**Interfaces:**
- Produces: `PipelineState.MEDIA_BUNDLE`.
- Produces: `GenerateMediaStep(service)` and `ValidateMediaStep(validator)`.
- Consumes: the media service injected through workflow construction.

- [ ] **Step 1: Write a failing step-order and failure-blocking test**

Use recording steps and assert:

```python
assert [step.name for step in workflow.build_steps()] == [
    "validate",
    "generate_media",
    "validate_media",
    "render",
    "publish",
    "record",
]
```

When the fake generation service raises, assert `renderer.calls == 0`,
`publisher.calls == 0`, and result `failed_step == "generate_media"`.

- [ ] **Step 2: Run and verify RED**

Run:

```powershell
pytest tests/test_media_pipeline.py -q
```

- [ ] **Step 3: Add pipeline state and injected steps**

Implement:

```python
class PipelineState(str, Enum):
    RENDER_RESULT = "render_result"
    PUBLISH_RESULT = "publish_result"
    VALIDATION = "validation"
    WARNINGS = "warnings"
    STEP_RESULTS = "step_results"
    MEDIA_BUNDLE = "media_bundle"


class GenerateMediaStep(PipelineStep):
    name = "generate_media"

    def __init__(self, service: MediaGenerationService):
        self._service = service

    def execute(self, ctx: PipelineContext) -> StepResult:
        if ctx.mode == "preview" or not ctx.config.media.enabled:
            return StepResult(status=StepStatus.SKIPPED, message="Media generation skipped")
        try:
            bundle = self._service.generate_daily(ctx.article)
        except AgnesAPIError as exc:
            return StepResult(
                status=StepStatus.FAILED,
                message=str(exc),
                retryable=exc.retryable,
            )
        ctx.set(PipelineState.MEDIA_BUNDLE, bundle)
        ctx.article.cover = bundle.cover.local_path
        return StepResult(status=StepStatus.SUCCESS, message="Media generated")


class ValidateMediaStep(PipelineStep):
    name = "validate_media"

    def __init__(self, validator: MediaValidator):
        self._validator = validator

    def execute(self, ctx: PipelineContext) -> StepResult:
        if ctx.mode == "preview" or not ctx.config.media.enabled:
            return StepResult(status=StepStatus.SKIPPED, message="Media validation skipped")
        bundle = ctx.get(PipelineState.MEDIA_BUNDLE)
        errors = ["Media bundle missing"] if bundle is None else self._validator.validate(bundle)
        if errors:
            return StepResult(
                status=StepStatus.FAILED,
                message=f"Media validation failed: {'; '.join(errors)}",
            )
        return StepResult(status=StepStatus.SUCCESS, message="Media validation passed")
```

Preview mode skips Agnes. Dry-run still generates and validates local media because it is the production preflight path.

- [ ] **Step 4: Add a failing preview and dry-run test**

Assert preview makes zero provider calls; dry-run produces a bundle but makes zero WeChat calls.

- [ ] **Step 5: Implement mode behavior and run tests**

Run:

```powershell
pytest tests/test_media_pipeline.py -q
pytest -q
```

- [ ] **Step 6: Commit only Task 4 files**

```powershell
git add publishing/pipeline.py publishing/steps.py publishing/workflow.py publishing/factory.py tests/test_media_pipeline.py
git commit -m "feat: block publication on media generation failures"
```

### Task 5: WeChat body images and reusable video

**Files:**
- Modify: `zerorealm-data/publishing/wechat/client.py`
- Modify: `zerorealm-data/publishing/wechat/renderer.py`
- Modify: `zerorealm-data/publishing/wechat/publisher.py`
- Modify: `zerorealm-data/publishing/models.py`
- Test: `zerorealm-data/tests/test_wechat_media.py`
- Test: `zerorealm-data/tests/test_wechat_publishing.py`

**Interfaces:**
- Produces: `WechatClient.upload_permanent_video(path, title, introduction) -> dict`.
- Produces: `WechatVideoEmbedder.render(media_id, title) -> str`.
- Consumes: `RenderResult.media`, `RenderResult.video`, local placeholder URLs.

- [ ] **Step 1: Write failing client tests for permanent video upload**

Assert the multipart request uses:

```text
POST /cgi-bin/material/add_material?type=video
```

with a `description` JSON part containing a short title and introduction, and that WeChat API errors redact credentials.

- [ ] **Step 2: Run and verify RED**

Run:

```powershell
pytest tests/test_wechat_media.py -q
```

- [ ] **Step 3: Implement the client upload method**

Keep the existing image upload methods unchanged except for shared safe response handling.

- [ ] **Step 4: Write failing renderer/publisher tests**

Create a media bundle and assert:

- three stable local tokens are inserted at semantic positions;
- publisher uploads each body image once and replaces every token with the returned WeChat CDN URL;
- video is uploaded before draft creation;
- video embed HTML contains the returned video media identifier;
- any body image or video failure returns `PublishStatus.FAILED`;
- `create_draft` is never called after media failure.

- [ ] **Step 5: Run and verify RED**

Run:

```powershell
pytest tests/test_wechat_media.py tests/test_wechat_publishing.py -q
```

- [ ] **Step 6: Implement image replacement and isolated video embed adapter**

Add `video: MediaAsset | None` to `RenderResult`. Keep WeChat-specific markup in
`WechatVideoEmbedder`; Renderer uses a stable placeholder and Publisher replaces it only after successful upload.

- [ ] **Step 7: Run focused and full tests**

Run:

```powershell
pytest tests/test_wechat_media.py tests/test_wechat_publishing.py -q
pytest -q
```

- [ ] **Step 8: Commit only Task 5 files**

```powershell
git add publishing/wechat publishing/models.py tests/test_wechat_media.py tests/test_wechat_publishing.py
git commit -m "feat: publish Agnes images and video to WeChat"
```

### Task 6: Homepage media generation command

**Files:**
- Create: `zerorealm-data/publishing/media_generation/homepage.py`
- Create: `zerorealm-data/generate_media.py`
- Modify: `zerorealm-data/tests/test_media_generation.py`
- Create: `zerorealm-website/public/media/home/README.md`

**Interfaces:**
- Produces: `generate_homepage_media(website_root, force=False)`.
- Produces CLI: `python generate_media.py homepage [--force] [--website-root PATH]`.
- Consumes: the same Agnes client/service and `AGNES_API_KEY`.

- [ ] **Step 1: Write failing no-overwrite and force-overwrite tests**

Assert:

```python
with pytest.raises(FileExistsError):
    generate_homepage_media(existing_website_root, force=False)

result = generate_homepage_media(existing_website_root, force=True)
assert (home_dir / "homepage-media.json").exists()
```

Also assert missing `AGNES_API_KEY` fails before any output file is written.

- [ ] **Step 2: Run and verify RED**

Run:

```powershell
pytest tests/test_media_generation.py -q
```

- [ ] **Step 3: Implement safe staging and atomic directory promotion**

Generate into a temporary sibling directory. Validate all media, then replace individual target files and finally the manifest. Do not delete the existing directory before a complete replacement is ready.

- [ ] **Step 4: Add CLI argument tests and implement CLI**

Cover `homepage`, `--force`, and `--website-root`. Return exit code 1 with a concise redacted error on failure.

- [ ] **Step 5: Run tests and CLI help**

Run:

```powershell
pytest tests/test_media_generation.py -q
python generate_media.py --help
```

- [ ] **Step 6: Commit Task 6 files in their respective repos**

Data repo:

```powershell
git add publishing/media_generation/homepage.py generate_media.py tests/test_media_generation.py
git commit -m "feat: add homepage Agnes media command"
```

Website repo:

```powershell
git add public/media/home/README.md
git commit -m "docs: define homepage media asset contract"
```

### Task 7: Render homepage image and video

**Files:**
- Create: `zerorealm-website/lib/home-media.ts`
- Create: `zerorealm-website/components/home/HomeMedia.tsx`
- Modify: `zerorealm-website/components/home/Hero.tsx`
- Modify: `zerorealm-website/app/page.tsx`
- Create: `zerorealm-website/tests/home-media.test.ts`

**Interfaces:**
- Produces: `getHomeMedia(): HomeMediaManifest | null`.
- Produces: `<HomeMedia manifest={manifest} />`.
- Consumes: `/public/media/home/homepage-media.json`.

- [ ] **Step 1: Read the installed Next.js 16 image and video/static-file guides**

Use `rg` under `node_modules/next/dist/docs/` to locate the exact installed guidance before writing framework code, as required by `AGENTS.md`.

- [ ] **Step 2: Write failing manifest-loader tests**

Test a valid manifest and a missing manifest. The missing case returns `null`; malformed paths that escape `/media/home/` are rejected.

- [ ] **Step 3: Run and verify RED**

Run:

```powershell
npm test
```

- [ ] **Step 4: Implement the typed loader**

Use `fs.readFileSync` only on the known manifest path. Validate that public URLs begin with `/media/home/` and return a narrowed object.

- [ ] **Step 5: Add failing markup contract tests**

Render or inspect component source with the existing lightweight Node test approach and assert:

- image alt text exists;
- width/height are supplied;
- video includes `controls`, `preload="metadata"`, and `poster`;
- video does not include `autoPlay` or `loop`.

- [ ] **Step 6: Implement the component and homepage integration**

Hero becomes a responsive text/media grid. The video lives in a separate, calm showcase section, not as a background.

- [ ] **Step 7: Run website verification**

Run:

```powershell
npm test
npm run lint
npm run build
```

Expected: all PASS with no new warnings.

- [ ] **Step 8: Commit only Task 7 files**

```powershell
git add lib/home-media.ts components/home/HomeMedia.tsx components/home/Hero.tsx app/page.tsx tests/home-media.test.ts
git commit -m "feat: display generated homepage media"
```

### Task 8: End-to-end safety and operator documentation

**Files:**
- Modify: `zerorealm-data/README.md`
- Modify: `zerorealm-data/.gitignore`
- Modify: `zerorealm-website/README.md`
- Modify: `zerorealm-data/tests/test_integration.py`

**Interfaces:**
- Documents exact environment variables and commands.
- Verifies a fake end-to-end daily run blocks before draft creation on video failure.

- [ ] **Step 1: Write the failing end-to-end blocking test**

Build a real `PublishWorkflow` with fake Agnes and WeChat transports. Force video failure and assert:

```python
assert result.status == PublishStatus.FAILED
assert result.failed_step == "generate_media"
assert fake_wechat.created == []
```

- [ ] **Step 2: Run and verify RED**

Run:

```powershell
pytest tests/test_integration.py -q
```

- [ ] **Step 3: Complete minimal wiring until the end-to-end test passes**

Wire client construction from `AGNES_API_KEY`, media config, and workflow dependency injection. Do not add fallback images or previous-day reuse.

- [ ] **Step 4: Add operator documentation**

Document:

```powershell
$env:AGNES_API_KEY="<new-rotated-key>"
python generate_media.py homepage --website-root ..\zerorealm-website
python publish.py --channel wechat --date YYYY-MM-DD --dry-run
python publish.py --channel wechat --date YYYY-MM-DD --publish
```

Explicitly state that the key previously pasted into chat must not be reused.

- [ ] **Step 5: Ignore transient media staging only**

Ignore `*.partial` and local test/staging directories. Do not ignore committed homepage assets or daily production manifests that operators need to retain.

- [ ] **Step 6: Run final verification in both repos**

Data repo:

```powershell
pytest -q
ruff check .
```

Website repo:

```powershell
npm test
npm run lint
npm run build
```

Also run:

```powershell
git grep -l -E "sk-[A-Za-z0-9_-]{20,}"
git status --short
```

Expected: no exposed key, all checks pass, and only intended files remain changed.

- [ ] **Step 7: Commit Task 8 files without staging unrelated work**

Data repo:

```powershell
git add README.md .gitignore tests/test_integration.py
git commit -m "docs: document Agnes media operations"
```

Website repo:

```powershell
git add README.md
git commit -m "docs: document homepage media refresh"
```

## Plan Self-Review

- Every design requirement maps to Tasks 1–8.
- Provider, pipeline, WeChat, homepage command, frontend, security, and failure-blocking behavior each have a focused test-first cycle.
- Interfaces consumed by later tasks are defined in earlier tasks.
- No task requires the exposed chat key or a live production publish.
- Live WeChat account capability remains a deployment verification gate; automated tests prove that unsupported video upload/embed blocks publication safely.
