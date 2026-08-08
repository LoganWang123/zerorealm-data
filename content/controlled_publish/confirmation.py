"""Human confirmation tokens bound to RC revision + fingerprint."""

from __future__ import annotations

import hashlib
import re

from content.controlled_publish.errors import (
    CONFIRMATION_INVALID,
    CONFIRMATION_REQUIRED,
    ControlledPublishError,
)
from content.release_candidate import ReleaseCandidate

_TOKEN_RE = re.compile(r"^CONFIRM-[A-Z0-9]{6}$")


def build_confirmation_token(rc: ReleaseCandidate) -> str:
    """Short phrase derived from identity — not 'yes'."""
    material = "|".join(
        [
            rc.release_candidate_id,
            rc.revision or "",
            rc.content_fingerprint or "",
            rc.content_id,
            rc.content_type,
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest().upper()
    return f"CONFIRM-{digest[:6]}"


def validate_confirmation_token(rc: ReleaseCandidate, token: str | None) -> str:
    expected = build_confirmation_token(rc)
    provided = (token or "").strip().upper()
    if not provided:
        raise ControlledPublishError(CONFIRMATION_REQUIRED, "Missing --confirm token")
    if provided in ("YES", "Y", "TRUE", "OK", "CONFIRM"):
        raise ControlledPublishError(
            CONFIRMATION_INVALID,
            "Weak confirmation rejected; use CONFIRM-XXXXXX bound to revision/fingerprint",
        )
    if not _TOKEN_RE.match(provided):
        raise ControlledPublishError(CONFIRMATION_INVALID, f"Malformed confirmation: {token}")
    if provided != expected:
        raise ControlledPublishError(
            CONFIRMATION_INVALID,
            "Confirmation does not match current revision/fingerprint",
        )
    return expected
