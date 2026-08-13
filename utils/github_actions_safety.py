"""GitHub Actions safety helpers (defense in depth).

When ``GITHUB_ACTIONS=true``, collection must be local-only and the Daily
Pipeline must not LLM-generate or publish. The slim Daily Collection YAML
is the primary control; these helpers remain a runtime kill switch if a
legacy workflow or injected secret reappears.

Do not weaken the unit tests while generate/publish skip behaviour is
required.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

# Forced onto subsequent Actions steps via GITHUB_ENV. Values are constants;
# callers must never log the previous process environment for these keys.
SAFE_GITHUB_ENV_OVERRIDES: tuple[tuple[str, str], ...] = (
    ("SYNC_PUBLIC_BUNDLE", "false"),
    ("SYNC_LEGACY_DAILY_MDX", "false"),
    ("WEBSITE_REPO_TOKEN", ""),
    ("WECHAT_APPID", ""),
    ("WECHAT_SECRET", ""),
    ("ZEROREALM_LOCAL_IMAGE_CMD", ""),
)

GENERATION_SKIP_REASON = (
    "GITHUB_ACTIONS=true: skip generate_daily LLM "
    "(collection-only transition; legacy workflow maps exit 2 to generated=false). "
    "Credentials are not read or logged."
)


def is_github_actions(environ: Mapping[str, str] | None = None) -> bool:
    """True only when GitHub Actions set GITHUB_ACTIONS=true. Local runs stay intact."""
    env = os.environ if environ is None else environ
    return str(env.get("GITHUB_ACTIONS", "")).strip().lower() == "true"


def write_github_actions_safe_env(github_env_path: str | os.PathLike[str] | None) -> None:
    """Append safe overrides to a GITHUB_ENV file.

    Never reads or logs previous values of the overridden keys.
    No-op when *github_env_path* is missing (non-Actions or tests without a file).
    """
    if not github_env_path:
        return
    path = Path(github_env_path)
    with path.open("a", encoding="utf-8") as handle:
        for name, value in SAFE_GITHUB_ENV_OVERRIDES:
            handle.write(f"{name}={value}\n")


def configure_github_actions_safety(
    environ: Mapping[str, str] | None = None,
    github_env_path: str | os.PathLike[str] | None = None,
) -> bool:
    """If running on Actions, write GITHUB_ENV overrides and return True (force local-only)."""
    env = os.environ if environ is None else environ
    if not is_github_actions(env):
        return False
    path = env.get("GITHUB_ENV") if github_env_path is None else github_env_path
    write_github_actions_safe_env(path)
    return True


def legacy_pipeline_publish_steps_run(
    *,
    website_repo_token: str,
    sync_public_bundle: str,
    generated: str,
) -> dict[str, bool]:
    """Evaluate old Daily Pipeline ``if:`` predicates after a GITHUB_ENV override.

    Mirrors origin ``daily-crawl.yaml`` (Daily Pipeline) step conditions. Used by
    tests to prove publish/images/verify skip when token is emptied and
    generated=false / SYNC_PUBLIC_BUNDLE=false.
    """
    token_present = website_repo_token != ""
    generated_true = generated == "true"
    sync_bundle = sync_public_bundle == "true"
    return {
        "checkout_website": token_present,
        "website_token_warning": not token_present,
        "generate_images": token_present and generated_true,
        "publish_website": token_present and (generated_true or sync_bundle),
        "verify_production": token_present and generated_true,
        # No `if` on origin: local export still runs; it does not git-push.
        "export_public_bundle": True,
    }
