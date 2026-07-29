# Homepage Brand Media Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate one text-free ZeroRealm AI homepage image and three distinct Agnes video scenes, then assemble them into a non-looping 15-second brand film that accurately communicates retail intelligence and decision support.

**Architecture:** Keep Agnes transport inside `AgnesClient`, express the creative contract in versioned deterministic prompts, and add a focused FFmpeg assembly module for normalization and transitions. The homepage orchestrator writes every provider response to resumable scene partials, validates the assembled deliverables, and atomically replaces the website files and manifest only after every gate passes.

**Tech Stack:** Python 3.14, requests, pytest, Ruff, Agnes image/video APIs, FFmpeg/ffprobe, Next.js 16, TypeScript.

## Global Constraints

- Use Agnes for one homepage image and three independent video scene generations.
- Final image must be a valid 1920×1080 PNG.
- Final video must be 1920×1080 H.264 `yuv420p` MP4 with a duration from 14 to 16 seconds.
- Do not loop, reverse, freeze, or repeat a generated scene to fill time.
- Do not render words, subtitles, logos, watermarks, fake UI copy, neon brand lettering, cartoon people, toy-model imagery, chips, or factory-line subjects.
- Preserve the existing published homepage image, video, and manifest unless every new artifact passes validation.
- Read credentials only from `AGNES_API_KEY`; never log, persist, or expose the key.
- Support `FFMPEG_PATH`, `FFPROBE_PATH`, and `FFMPEG_VIDEO_ENCODER` environment configuration without changing system settings.

---

### Task 1: Versioned three-scene creative contract

**Files:**
- Modify: `publishing/media_generation/prompts.py`
- Modify: `tests/test_media_generation.py`

**Interfaces:**
- Consumes: existing `PromptSet` and `build_homepage_prompts()`.
- Produces: `PromptSet.video_scenes: tuple[str, ...]` and homepage prompt version `homepage-v2`.

- [ ] **Step 1: Write the failing prompt-contract test**

```python
from publishing.media_generation.prompts import build_homepage_prompts


def test_homepage_prompts_define_three_distinct_retail_intelligence_scenes():
    prompts = build_homepage_prompts()

    assert prompts.version == "homepage-v2"
    assert len(prompts.video_scenes) == 3
    assert "零售信号" in prompts.video_scenes[0]
    assert "结构化知识" in prompts.video_scenes[1]
    assert "经营决策" in prompts.video_scenes[2]
    for prompt in (prompts.cover, *prompts.video_scenes):
        assert "禁止任何文字" in prompt
        assert "不循环" in prompt
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
python -m pytest tests/test_media_generation.py::test_homepage_prompts_define_three_distinct_retail_intelligence_scenes -q -p no:cacheprovider --basetemp=.test-tmp/prompts-red
```

Expected: FAIL because `PromptSet` has no `video_scenes` and the version is still `homepage-v1`.

- [ ] **Step 3: Add the prompt field and exact homepage-v2 prompts**

Extend the dataclass without changing daily media behavior:

```python
@dataclass(frozen=True)
class PromptSet:
    cover: str
    body_images: list[str]
    video: str
    version: str
    video_scenes: tuple[str, ...] = ()
```

Set `HOMEPAGE_PROMPT_VERSION = "homepage-v2"`. Build the homepage cover around a real retail environment, right-side decision subject, restrained data relationships, and clean left negative space. Build three self-contained 5-second prompts in this fixed order:

```python
scenes = (
    f"{common} 第一镜：零售信号发现。真实门店、商品、客流和市场变化形成克制的数据光点；稳定向前运镜。禁止任何文字、Logo、水印和伪界面文案；不循环、不倒放。",
    f"{common} 第二镜：结构化知识形成。不同零售信号自然汇聚为清晰的关系网络、趋势层次和知识结构；连续横向运镜。禁止任何文字、Logo、水印、芯片和工厂意象；不循环、不倒放。",
    f"{common} 第三镜：经营决策支持。分析结果进入真实商业决策场景，体现趋势判断、机会识别和行动方向；镜头稳定收束并留下自然片尾空间。禁止任何文字、Logo、水印和伪界面文案；不循环、不倒放。",
)
```

Retain `video` as the shared full-film description for backward compatibility and assign `video_scenes=scenes`.

- [ ] **Step 4: Run focused and existing prompt tests**

Run:

```powershell
python -m pytest tests/test_media_generation.py -q -p no:cacheprovider --basetemp=.test-tmp/prompts-green
python -m ruff check publishing/media_generation/prompts.py tests/test_media_generation.py
```

Expected: all tests and Ruff pass.

- [ ] **Step 5: Commit the prompt contract**

```powershell
git add publishing/media_generation/prompts.py tests/test_media_generation.py
git commit -m "feat: define homepage brand film scenes"
```

### Task 2: Deterministic FFmpeg media normalization and assembly

**Files:**
- Create: `publishing/media_generation/assembly.py`
- Create: `tests/test_media_assembly.py`

**Interfaces:**
- Consumes: `FFMPEG_PATH`, optional `FFMPEG_VIDEO_ENCODER`, one raw image path, and exactly three raw MP4 paths.
- Produces:
  - `resolve_ffmpeg() -> str`
  - `normalize_homepage_image(source: Path, output: Path) -> None`
  - `assemble_homepage_video(clips: tuple[Path, Path, Path], output: Path) -> None`

- [ ] **Step 1: Write failing executable-resolution tests**

```python
def test_resolve_ffmpeg_prefers_explicit_existing_path(tmp_path, monkeypatch):
    executable = tmp_path / "ffmpeg.exe"
    executable.write_bytes(b"binary")
    monkeypatch.setenv("FFMPEG_PATH", str(executable))
    monkeypatch.setattr("shutil.which", lambda name: None)

    assert resolve_ffmpeg() == str(executable)


def test_resolve_ffmpeg_rejects_invalid_explicit_path(tmp_path, monkeypatch):
    monkeypatch.setenv("FFMPEG_PATH", str(tmp_path / "missing.exe"))

    with pytest.raises(ValueError, match="FFMPEG_PATH"):
        resolve_ffmpeg()
```

- [ ] **Step 2: Run the resolver tests and verify RED**

Run:

```powershell
python -m pytest tests/test_media_assembly.py -q -p no:cacheprovider --basetemp=.test-tmp/assembly-resolver-red
```

Expected: collection fails because `publishing.media_generation.assembly` does not exist.

- [ ] **Step 3: Implement `resolve_ffmpeg`**

```python
def resolve_ffmpeg() -> str:
    configured = os.getenv("FFMPEG_PATH")
    if configured:
        if not Path(configured).is_file():
            raise ValueError("FFMPEG_PATH does not point to a file")
        return configured
    executable = shutil.which("ffmpeg")
    if not executable:
        raise ValueError("ffmpeg is required to assemble homepage media")
    return executable
```

- [ ] **Step 4: Write failing subprocess-contract tests**

Mock `subprocess.run` and assert:

```python
def test_normalize_homepage_image_outputs_exact_png_contract(tmp_path, monkeypatch):
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.write_bytes(b"binary")
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    output = tmp_path / "ready.png"
    calls = []
    monkeypatch.setenv("FFMPEG_PATH", str(ffmpeg))
    monkeypatch.setattr(
        "publishing.media_generation.assembly.subprocess.run",
        lambda command, **kwargs: calls.append((command, kwargs)),
    )

    normalize_homepage_image(source, output)

    command, kwargs = calls[0]
    assert command[0] == str(ffmpeg)
    assert command[command.index("-vf") + 1] == "scale=1920:1080"
    assert command[-1] == str(output)
    assert kwargs["check"] is True
    assert kwargs["timeout"] == 180


def test_assemble_homepage_video_uses_three_inputs_without_looping(
    tmp_path,
    monkeypatch,
):
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.write_bytes(b"binary")
    clips = tuple(tmp_path / f"scene-{index}.mp4" for index in range(1, 4))
    for clip in clips:
        clip.write_bytes(b"video")
    output = tmp_path / "showcase.ready.mp4"
    calls = []
    monkeypatch.setenv("FFMPEG_PATH", str(ffmpeg))
    monkeypatch.setattr(
        "publishing.media_generation.assembly.subprocess.run",
        lambda command, **kwargs: calls.append((command, kwargs)),
    )

    assemble_homepage_video(clips, output)

    command, kwargs = calls[0]
    filter_graph = command[command.index("-filter_complex") + 1]
    assert command.count("-i") == 3
    assert "-stream_loop" not in command
    assert filter_graph.count("xfade") == 2
    assert command[command.index("-pix_fmt") + 1] == "yuv420p"
    assert command[-1] == str(output)
    assert kwargs["check"] is True
```

Also assert the function rejects any number of clips other than three before invoking FFmpeg.

- [ ] **Step 5: Implement normalization and three-scene assembly**

Use `subprocess.run(command, check=True, capture_output=True, text=True, timeout=180)`. Image normalization uses:

```text
-vf scale=1920:1080 -frames:v 1 -f image2
```

Video assembly uses three `-i` inputs and one filter graph. For each input: reset timestamps, trim to five seconds, scale down to fit 1920×1080, pad with `0x071525`, force 24 fps, and format as `yuv420p`. Join scene 1 to 2 and scene 2 to 3 with 0.25-second `xfade=fade` transitions at offsets 4.75 and 9.50. Encode with `os.getenv("FFMPEG_VIDEO_ENCODER", "libx264")`, `-b:v 6M`, `-pix_fmt yuv420p`, `-an`, and `-movflags +faststart`.

On `subprocess.CalledProcessError`, raise a `ValueError("ffmpeg failed to assemble homepage media")` without including provider secrets or the full environment.

- [ ] **Step 6: Run assembly tests and Ruff**

Run:

```powershell
python -m pytest tests/test_media_assembly.py -q -p no:cacheprovider --basetemp=.test-tmp/assembly-green
python -m ruff check publishing/media_generation/assembly.py tests/test_media_assembly.py
```

Expected: all tests and Ruff pass.

- [ ] **Step 7: Commit the assembly boundary**

```powershell
git add publishing/media_generation/assembly.py tests/test_media_assembly.py
git commit -m "feat: assemble homepage brand film"
```

### Task 3: Resumable three-scene homepage generation

**Files:**
- Modify: `publishing/media_generation/homepage.py`
- Modify: `tests/test_media_generation.py`

**Interfaces:**
- Consumes:
  - `PromptSet.video_scenes`
  - `normalize_homepage_image(source: Path, output: Path) -> None`
  - `assemble_homepage_video(clips: tuple[Path, Path, Path], output: Path) -> None`
- Produces: the existing `generate_homepage_media(client, website_root, *, force=False, validator=None, image_normalizer=normalize_homepage_image, video_assembler=assemble_homepage_video) -> Path` contract with one image call, three video calls, per-scene recovery, and atomic final replacement.

- [ ] **Step 1: Replace the old call-count test with a failing three-scene test**

Inject normalizer and assembler callables into `generate_homepage_media`:

```python
manifest_path = generate_homepage_media(
    client=client,
    website_root=website_root,
    force=False,
    validator=lambda image, video: None,
    image_normalizer=lambda source, output: output.write_bytes(source.read_bytes()),
    video_assembler=lambda clips, output: output.write_bytes(
        b"\x00\x00\x00\x18ftypmp42assembled"
    ),
)

assert len(client.image_calls) == 1
assert len(client.video_calls) == 3
assert [call[0] for call in client.video_calls] == list(
    build_homepage_prompts().video_scenes
)
```

- [ ] **Step 2: Add failing granular-resume and failure-safety tests**

Cover these cases:

```python
def _copy_image(source, output):
    output.write_bytes(source.read_bytes())


def _write_assembled_video(clips, output):
    assert len(clips) == 3
    output.write_bytes(b"\x00\x00\x00\x18ftypmp42assembled")


def test_homepage_generation_resumes_existing_image_and_video_scenes(tmp_path):
    website_root = tmp_path / "website"
    home_dir = website_root / "public" / "media" / "home"
    home_dir.mkdir(parents=True)
    (home_dir / "hero.raw.png.partial").write_bytes(b"raw-image")
    for index in range(1, 4):
        (home_dir / f"scene-{index:02d}.mp4.partial").write_bytes(
            f"scene-{index}".encode()
        )
    client = FakeAgnesClient()

    generate_homepage_media(
        client,
        website_root,
        validator=lambda image, video: None,
        image_normalizer=_copy_image,
        video_assembler=_write_assembled_video,
    )

    assert client.image_calls == []
    assert client.video_calls == []


def test_homepage_generation_only_requests_missing_scene(tmp_path):
    website_root = tmp_path / "website"
    home_dir = website_root / "public" / "media" / "home"
    home_dir.mkdir(parents=True)
    (home_dir / "hero.raw.png.partial").write_bytes(b"raw-image")
    (home_dir / "scene-01.mp4.partial").write_bytes(b"scene-1")
    (home_dir / "scene-03.mp4.partial").write_bytes(b"scene-3")
    client = FakeAgnesClient()

    generate_homepage_media(
        client,
        website_root,
        validator=lambda image, video: None,
        image_normalizer=_copy_image,
        video_assembler=_write_assembled_video,
    )

    prompts = build_homepage_prompts()
    assert len(client.video_calls) == 1
    assert client.video_calls[0][0] == prompts.video_scenes[1]


def test_homepage_assembly_failure_preserves_published_files(tmp_path):
    website_root = tmp_path / "website"
    home_dir = website_root / "public" / "media" / "home"
    home_dir.mkdir(parents=True)
    image_path = home_dir / "hero.png"
    video_path = home_dir / "showcase.mp4"
    manifest_path = home_dir / "homepage-media.json"
    image_path.write_bytes(b"published-image")
    video_path.write_bytes(b"published-video")
    manifest_path.write_bytes(b"published-manifest")
    (home_dir / "hero.raw.png.partial").write_bytes(b"raw-image")
    for index in range(1, 4):
        (home_dir / f"scene-{index:02d}.mp4.partial").write_bytes(
            f"scene-{index}".encode()
        )

    with pytest.raises(ValueError, match="assembly failed"):
        generate_homepage_media(
            FakeAgnesClient(),
            website_root,
            force=True,
            image_normalizer=_copy_image,
            video_assembler=lambda clips, output: (
                _ for _ in ()
            ).throw(ValueError("assembly failed")),
        )

    assert image_path.read_bytes() == b"published-image"
    assert video_path.read_bytes() == b"published-video"
    assert manifest_path.read_bytes() == b"published-manifest"
```

- [ ] **Step 3: Run focused tests and verify RED**

Run:

```powershell
python -m pytest tests/test_media_generation.py -q -p no:cacheprovider --basetemp=.test-tmp/homepage-red
```

Expected: failures for missing injected callables, one-video behavior, and all-or-nothing partial recovery.

- [ ] **Step 4: Implement granular generation and recovery**

Change the function signature to:

```python
def generate_homepage_media(
    client: AgnesClient,
    website_root: str | Path,
    *,
    force: bool = False,
    validator: Callable[[Path, Path], None] | None = None,
    image_normalizer: Callable[[Path, Path], None] = normalize_homepage_image,
    video_assembler: Callable[[tuple[Path, Path, Path], Path], None] = assemble_homepage_video,
) -> Path:
```

Use these paths:

```python
image_raw = home_dir / "hero.raw.png.partial"
image_ready = home_dir / "hero.ready.png"
scene_paths = tuple(
    home_dir / f"scene-{index:02d}.mp4.partial"
    for index in range(1, 4)
)
video_ready = home_dir / "showcase.ready.mp4"
```

Generate only missing raw files. Write each Agnes response immediately and reject empty bytes. Normalize the image only when `hero.ready.png` is absent. Assemble only when `showcase.ready.mp4` is absent. Validate the two ready files, read their final bytes, replace `hero.png` and `showcase.mp4`, write the manifest partial, then remove raw scene partials only after the manifest replacement succeeds.

Do not reuse the legacy `hero.png.partial` plus `showcase.mp4.partial` pair for homepage-v2; its contents cannot prove that three distinct scenes were generated.

- [ ] **Step 5: Tighten final homepage validation**

Require:

```python
if (image.width, image.height) != (1920, 1080):
    raise ValueError("Homepage image must be 1920x1080")
if (video.width, video.height) != (1920, 1080):
    raise ValueError("Homepage video must be 1920x1080")
if not 14 <= video.duration_seconds <= 16:
    raise ValueError("Homepage video duration must be between 14 and 16 seconds")
```

Update the manifest to use the probed final dimensions and duration rounded to three decimals, while retaining the public paths and SHA-256 fields.

- [ ] **Step 6: Run homepage, client, and assembly tests**

Run:

```powershell
python -m pytest tests/test_media_generation.py tests/test_agnes_client.py tests/test_media_assembly.py -q -p no:cacheprovider --basetemp=.test-tmp/homepage-green
python -m ruff check publishing/media_generation tests/test_media_generation.py tests/test_agnes_client.py tests/test_media_assembly.py
```

Expected: all tests and Ruff pass.

- [ ] **Step 7: Commit the resumable pipeline**

```powershell
git add publishing/media_generation/homepage.py tests/test_media_generation.py
git commit -m "feat: generate resumable homepage brand film"
```

### Task 4: Document and verify the local FFmpeg contract

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `tests/test_media_generation.py`

**Interfaces:**
- Consumes: `client_from_environment()` and the assembly resolver.
- Produces: documented `FFMPEG_PATH`, `FFPROBE_PATH`, and `FFMPEG_VIDEO_ENCODER` configuration for `generate_media.py homepage --force`.

- [ ] **Step 1: Write a failing environment-contract test**

```python
def test_homepage_environment_documents_media_tool_paths():
    example = Path(".env.example").read_text(encoding="utf-8")
    assert "FFMPEG_PATH=" in example
    assert "FFPROBE_PATH=" in example
    assert "FFMPEG_VIDEO_ENCODER=" in example
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
python -m pytest tests/test_media_generation.py::test_homepage_environment_documents_media_tool_paths -q -p no:cacheprovider --basetemp=.test-tmp/env-red
```

Expected: FAIL because the FFmpeg variables are not present.

- [ ] **Step 3: Document exact configuration and command**

Add commented variables to `.env.example`:

```dotenv
# FFMPEG_PATH=C:\path\to\ffmpeg.exe
# FFPROBE_PATH=C:\path\to\ffprobe.exe
# FFMPEG_VIDEO_ENCODER=libx264
```

Add a README section explaining that Windows builds without `libx264` may set `FFMPEG_VIDEO_ENCODER=h264_mf`, and that the command is:

```powershell
python generate_media.py homepage --website-root ..\zerorealm-website --force
```

State that the command makes one Agnes image request and up to three Agnes video requests, resumes complete scene partials, and does not replace published media on failure.

- [ ] **Step 4: Run documentation test and Ruff**

Run:

```powershell
python -m pytest tests/test_media_generation.py::test_homepage_environment_documents_media_tool_paths -q -p no:cacheprovider --basetemp=.test-tmp/env-green
python -m ruff check tests/test_media_generation.py
```

Expected: test and Ruff pass.

- [ ] **Step 5: Commit documentation**

```powershell
git add .env.example README.md tests/test_media_generation.py
git commit -m "docs: describe homepage media assembly"
```

### Task 5: Generate, inspect, and atomically publish the replacement assets

**Files:**
- Replace: `../zerorealm-website/public/media/home/hero.png`
- Replace: `../zerorealm-website/public/media/home/showcase.mp4`
- Replace: `../zerorealm-website/public/media/home/homepage-media.json`

**Interfaces:**
- Consumes: approved homepage-v2 prompts, configured Agnes credentials, FFmpeg, and ffprobe.
- Produces: final website media assets and a matching manifest.

- [ ] **Step 1: Verify configuration without printing secrets**

Run a presence-only check for `AGNES_API_KEY`, verify `FFMPEG_PATH` and `FFPROBE_PATH` point to executable files, and run both tools with `-version`. Do not echo the key or dump the process environment.

- [ ] **Step 2: Generate into resumable temporary files**

Run:

```powershell
python generate_media.py homepage --website-root ..\zerorealm-website --force
```

Expected: one new PNG response, three distinct video responses, one assembled MP4, successful validation, and the final manifest path.

- [ ] **Step 3: Perform visual QA before accepting the assets**

Inspect the full image and representative frames at approximately 1, 6, and 11 seconds. Reject and regenerate the affected raw asset if any frame contains:

- visible words, misspelled brand text, logos, watermarks, or fake UI copy;
- repeated scene content;
- chips, factories, toy models, or imagery unrelated to retail intelligence;
- stretched people or products, severe artifacts, or broken transitions.

Confirm that the three frames visibly progress from retail signals to structured knowledge to decision support.

- [ ] **Step 4: Verify technical metadata and hashes**

Use ffprobe to confirm H.264, 1920×1080, `yuv420p`, and 14–16 seconds. Compute SHA-256 for both files and compare them with `homepage-media.json`. Confirm there are no `*.partial` or `*.ready.*` files after successful publication.

- [ ] **Step 5: Run the complete data-repository verification**

Run:

```powershell
python -m pytest -q -p no:cacheprovider --basetemp=.test-tmp/final-data
python -m ruff check .
```

Expected: zero test failures and zero Ruff errors.

- [ ] **Step 6: Run the complete website verification**

From `../zerorealm-website`, run:

```powershell
npm test
npm run lint
npx tsc --noEmit
npm run build
```

Expected: all website tests pass, ESLint reports no errors, TypeScript exits zero, and Next.js completes the production build.

- [ ] **Step 7: Review final repository state**

Run `git status --short` and `git diff --check` in both repositories. Confirm only intended source, test, documentation, manifest, image, and video changes are present; preserve all unrelated user changes.
