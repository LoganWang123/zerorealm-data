"""Cross-channel canonical content contract (semantic + evidence, not verbatim).

Single source of truth: data/content-canonical/registry.json
Website receives a hashed mirror; channel packets must cite canonical_id/version.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "content-canonical" / "registry.json"
MIRROR_PATH = ROOT / "data" / "content-canonical" / "website-mirror.json"
PACKET_GLOB = "data/growth/content-packet-*.json"

ACTIVE_CHANNEL_STATUSES = frozenset(
    {
        "ready",
        "draft",
        "synced",
        "published",
        "production_ready",
        "production_ready_revision",
        "zhihu_published",
        "wechat_draft_updated",
    }
)


@dataclass
class ContractIssue:
    code: str
    path: str
    detail: str

    def format(self) -> str:
        return f"{self.code}: {self.path}: {self.detail}"


@dataclass
class ContractReport:
    issues: list[ContractIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def add(self, code: str, path: str, detail: str) -> None:
        self.issues.append(ContractIssue(code=code, path=path, detail=detail))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [i.format() for i in self.issues],
            "issue_count": len(self.issues),
        }


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_text(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_registry(path: Path | None = None) -> dict[str, Any]:
    return load_json(path or REGISTRY_PATH)


def family_index(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    families = registry.get("families") or []
    return {str(f["canonical_id"]): f for f in families}


def registry_sha256(path: Path | None = None) -> str:
    target = path or REGISTRY_PATH
    # Hash canonical JSON (sorted) so whitespace-only edits do not thrash mirrors.
    data = load_json(target)
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(canonical)


def build_website_mirror(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    """Generate website-compatible mirror with provenance hash."""
    reg = registry if registry is not None else load_registry()
    source_hash = registry_sha256()
    records: list[dict[str, Any]] = []
    for family in reg.get("families") or []:
        evidence = family.get("evidence") or {}
        sources = evidence.get("sources") or []
        primary_url = None
        publisher = None
        published_at = None
        evidence_level = None
        for src in sources:
            if isinstance(src, dict) and src.get("url") and src.get("url", "").startswith("http"):
                primary_url = src.get("url")
                publisher = src.get("publisher")
                published_at = src.get("published_at")
                evidence_level = src.get("evidence_level")
                break
        channels_out: dict[str, str] = {}
        for name, meta in (family.get("channels") or {}).items():
            if isinstance(meta, dict):
                channels_out[name] = str(meta.get("status") or "none")
            else:
                channels_out[name] = str(meta)
        cta = family.get("cta") or {}
        records.append(
            {
                "id": family["canonical_id"],
                "version": family["canonical_version"],
                "status": family.get("status", "approved"),
                "title": family.get("title"),
                "core_question": family.get("core_question"),
                "core_conclusion": family.get("core_conclusion"),
                "source": {
                    "url": primary_url,
                    "publisher": publisher,
                    "published_at": published_at,
                    "evidence_level": evidence_level,
                    "sources": sources,
                },
                "scope_guard": evidence.get("scope_guard"),
                "cta": cta,
                "channels": channels_out,
            }
        )
    return {
        "schema_version": 1,
        "mirror": {
            "source_repo": "zerorealm-data",
            "source_path": "data/content-canonical/registry.json",
            "source_sha256": source_hash,
            "consistency_means": "semantic_and_evidence_contract",
            "not_verbatim": True,
        },
        "policy": reg.get("policy"),
        "records": records,
        "families": reg.get("families") or [],
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _packet_contract_block(packet: dict[str, Any]) -> dict[str, Any]:
    block = packet.get("contract")
    return block if isinstance(block, dict) else {}


def _packet_tool_page(packet: dict[str, Any]) -> str | None:
    cta = packet.get("cta") or {}
    compliance = packet.get("compliance") or {}
    for candidate in (
        cta.get("tool_page"),
        compliance.get("tool_page"),
    ):
        if candidate:
            return str(candidate).rstrip("/")
    url = cta.get("url")
    if isinstance(url, str) and "smart-cabinet-weekly-review" in url:
        return url.split("?", 1)[0].rstrip("/")
    return None


def _packet_campaign(packet: dict[str, Any]) -> str | None:
    cta = packet.get("cta") or {}
    compliance = packet.get("compliance") or {}
    for candidate in (cta.get("campaign"), compliance.get("single_campaign")):
        if candidate:
            return str(candidate)
    return None


def validate_family_shape(family: dict[str, Any], report: ContractReport, path: str) -> None:
    cid = family.get("canonical_id")
    if not cid:
        report.add("FAMILY_MISSING_ID", path, "canonical_id required")
        return
    if family.get("canonical_version") is None:
        report.add("FAMILY_MISSING_VERSION", path, f"{cid}: canonical_version required")
    for key in ("core_question", "core_conclusion", "status"):
        if not family.get(key):
            report.add("FAMILY_INCOMPLETE", path, f"{cid}: missing {key}")
    evidence = family.get("evidence") or {}
    if not evidence.get("scope_guard"):
        report.add("FAMILY_INCOMPLETE", path, f"{cid}: missing evidence.scope_guard")
    if not evidence.get("sources"):
        report.add("FAMILY_INCOMPLETE", path, f"{cid}: missing evidence.sources")
    if "cta" not in family:
        report.add("FAMILY_INCOMPLETE", path, f"{cid}: missing cta")
    if "channels" not in family:
        report.add("FAMILY_INCOMPLETE", path, f"{cid}: missing channels")


def validate_packet_against_family(
    packet: dict[str, Any],
    family: dict[str, Any],
    *,
    path: str,
    report: ContractReport,
) -> None:
    cid = family["canonical_id"]
    expected_version = family["canonical_version"]
    got_id = packet.get("canonical_id")
    got_version = packet.get("canonical_version")
    if got_id != cid:
        report.add(
            "CANONICAL_ID_MISMATCH",
            path,
            f"expected {cid}, got {got_id!r}",
        )
    if got_version != expected_version:
        report.add(
            "VERSION_MISMATCH",
            path,
            f"{cid}: expected version {expected_version}, got {got_version!r}",
        )

    contract = _packet_contract_block(packet)
    expected_conclusion = family.get("core_conclusion")
    got_conclusion = contract.get("core_conclusion") or packet.get("core_conclusion")
    if got_conclusion != expected_conclusion:
        report.add(
            "CORE_CONCLUSION_DRIFT",
            path,
            f"{cid}: core_conclusion does not match family contract",
        )

    expected_scope = (family.get("evidence") or {}).get("scope_guard")
    got_scope = contract.get("scope_guard") or packet.get("scope_guard")
    if got_scope != expected_scope:
        report.add(
            "SCOPE_GUARD_DRIFT",
            path,
            f"{cid}: scope_guard does not match family contract",
        )

    # Evidence / source boundary: contract.sources_fingerprint or explicit sources list.
    family_sources = (family.get("evidence") or {}).get("sources") or []
    got_sources = contract.get("evidence_sources")
    if got_sources is not None and got_sources != family_sources:
        report.add(
            "EVIDENCE_SOURCE_DRIFT",
            path,
            f"{cid}: evidence_sources do not match family contract",
        )

    cta_target = ((family.get("cta") or {}).get("target")) or {}
    expected_tool = cta_target.get("tool_page")
    if expected_tool:
        expected_norm = str(expected_tool).rstrip("/")
        got_tool = _packet_tool_page(packet)
        # Keyword-only CTAs may omit tool_page; then campaign/keyword must still align.
        if got_tool and got_tool != expected_norm:
            report.add(
                "CTA_TARGET_DRIFT",
                path,
                f"{cid}: tool_page {got_tool!r} != {expected_norm!r}",
            )
        got_campaign = _packet_campaign(packet)
        expected_campaign = cta_target.get("campaign")
        if expected_campaign and got_campaign and got_campaign != expected_campaign:
            report.add(
                "CTA_TARGET_DRIFT",
                path,
                f"{cid}: campaign {got_campaign!r} != {expected_campaign!r}",
            )
        allowed = ((family.get("cta") or {}).get("allowed_copy_by_channel") or {}).get(
            packet.get("channel") or "",
            [],
        )
        copy = (packet.get("cta") or {}).get("copy")
        if allowed and copy and copy not in allowed:
            report.add(
                "CTA_TARGET_DRIFT",
                path,
                f"{cid}: cta.copy not in allowed_copy_by_channel for {packet.get('channel')}",
            )


def validate_registry(registry: dict[str, Any] | None = None) -> ContractReport:
    report = ContractReport()
    reg = registry if registry is not None else load_registry()
    families = reg.get("families") or []
    if not families:
        report.add("REGISTRY_EMPTY", str(REGISTRY_PATH), "no families defined")
        return report
    seen: set[str] = set()
    for family in families:
        cid = str(family.get("canonical_id") or "")
        path = f"family:{cid or '?'}"
        validate_family_shape(family, report, path)
        if cid in seen:
            report.add("DUPLICATE_CANONICAL_ID", path, cid)
        seen.add(cid)
    return report


def iter_content_packets(root: Path | None = None) -> list[Path]:
    base = root or ROOT
    return sorted(base.glob(PACKET_GLOB))


def validate_packets(
    registry: dict[str, Any] | None = None,
    *,
    root: Path | None = None,
) -> ContractReport:
    report = ContractReport()
    reg = registry if registry is not None else load_registry()
    index = family_index(reg)
    base = root or ROOT

    # Every content packet must declare canonical binding.
    for path in iter_content_packets(base):
        rel = path.relative_to(base).as_posix()
        packet = load_json(path)
        cid = packet.get("canonical_id")
        if not cid:
            report.add("MISSING_CANONICAL_REF", rel, "content packet lacks canonical_id")
            continue
        family = index.get(str(cid))
        if not family:
            report.add(
                "UNKNOWN_CANONICAL_ID",
                rel,
                f"canonical_id {cid!r} not in registry",
            )
            continue
        validate_packet_against_family(packet, family, path=rel, report=report)

    # Active channel refs declared by families must exist and cite back.
    for family in reg.get("families") or []:
        cid = family["canonical_id"]
        for channel, meta in (family.get("channels") or {}).items():
            if not isinstance(meta, dict):
                continue
            status = str(meta.get("status") or "none")
            refs = meta.get("refs") or []
            if status in ACTIVE_CHANNEL_STATUSES and channel in {"wechat", "zhihu"}:
                packet_refs = [
                    r
                    for r in refs
                    if isinstance(r, dict)
                    and r.get("kind") == "content_packet"
                    and r.get("repo", "zerorealm-data") == "zerorealm-data"
                ]
                if not packet_refs:
                    # planned/ready without artifact is allowed only for non-active
                    # or empty refs when status is planned — already filtered.
                    if status != "ready":
                        report.add(
                            "MISSING_CHANNEL_REF",
                            f"family:{cid}:{channel}",
                            f"active status {status!r} requires content_packet refs",
                        )
                    continue
                for ref in packet_refs:
                    rel = str(ref.get("path") or "")
                    abs_path = base / rel
                    if not abs_path.is_file():
                        report.add(
                            "MISSING_CHANNEL_REF",
                            f"family:{cid}:{channel}",
                            f"missing packet file {rel}",
                        )
                        continue
                    packet = load_json(abs_path)
                    if packet.get("canonical_id") != cid:
                        report.add(
                            "MISSING_CHANNEL_REF",
                            rel,
                            f"family {cid} lists this packet but packet.canonical_id="
                            f"{packet.get('canonical_id')!r}",
                        )
    return report


def validate_website_mirror(
    mirror: dict[str, Any],
    *,
    registry: dict[str, Any] | None = None,
    expected_source_sha256: str | None = None,
) -> ContractReport:
    report = ContractReport()
    reg = registry if registry is not None else load_registry()
    expected = expected_source_sha256 or registry_sha256()
    meta = mirror.get("mirror") or {}
    got = meta.get("source_sha256")
    if got != expected:
        report.add(
            "MIRROR_HASH_DRIFT",
            "website-mirror",
            f"source_sha256 {got!r} != registry {expected!r}",
        )
    # families in mirror must match SSoT
    if mirror.get("families") != (reg.get("families") or []):
        report.add(
            "MIRROR_FAMILY_DRIFT",
            "website-mirror",
            "mirror.families does not match registry.families",
        )
    records = mirror.get("records") or []
    by_id = {r.get("id"): r for r in records if isinstance(r, dict)}
    for family in reg.get("families") or []:
        cid = family["canonical_id"]
        record = by_id.get(cid)
        if not record:
            report.add("MIRROR_MISSING_RECORD", "website-mirror", f"missing record {cid}")
            continue
        if record.get("version") != family.get("canonical_version"):
            report.add(
                "VERSION_MISMATCH",
                "website-mirror",
                f"{cid}: record.version != family.canonical_version",
            )
        if record.get("core_conclusion") != family.get("core_conclusion"):
            report.add(
                "CORE_CONCLUSION_DRIFT",
                "website-mirror",
                f"{cid}: record.core_conclusion drift",
            )
        if record.get("scope_guard") != (family.get("evidence") or {}).get("scope_guard"):
            report.add(
                "SCOPE_GUARD_DRIFT",
                "website-mirror",
                f"{cid}: record.scope_guard drift",
            )
    return report


def check_all(
    *,
    root: Path | None = None,
    website_root: Path | None = None,
    require_website: bool = False,
) -> ContractReport:
    """Run full contract validation. Optionally compare sibling website mirror."""
    base = root or ROOT
    registry_path = base / "data" / "content-canonical" / "registry.json"
    registry = load_json(registry_path)
    report = validate_registry(registry)
    packet_report = validate_packets(registry, root=base)
    report.issues.extend(packet_report.issues)

    local_mirror_path = base / "data" / "content-canonical" / "website-mirror.json"
    if local_mirror_path.is_file():
        mirror = load_json(local_mirror_path)
        mirror_report = validate_website_mirror(mirror, registry=registry)
        report.issues.extend(mirror_report.issues)
        expected_mirror = build_website_mirror(registry)
        # Compare source hash + families; records rebuilt deterministically.
        if mirror.get("mirror", {}).get("source_sha256") != expected_mirror["mirror"][
            "source_sha256"
        ]:
            report.add(
                "MIRROR_HASH_DRIFT",
                local_mirror_path.relative_to(base).as_posix(),
                "committed mirror out of date; run sync_website_canonical_mirror.py",
            )
    else:
        report.add(
            "MIRROR_MISSING",
            "data/content-canonical/website-mirror.json",
            "local hashed mirror missing; run sync script",
        )

    site = website_root
    if site is None:
        sibling = base.parent / "zerorealm-website"
        ci_path = base / ".ci" / "zerorealm-website"
        if sibling.is_dir():
            site = sibling
        elif ci_path.is_dir():
            site = ci_path

    if site is not None:
        site_mirror = site / "data" / "content-canonical.json"
        if not site_mirror.is_file():
            if require_website:
                report.add(
                    "WEBSITE_MIRROR_MISSING",
                    str(site_mirror),
                    "website content-canonical.json missing",
                )
            # Incomplete/empty sibling paths are ignored unless require_website.
        else:
            remote = load_json(site_mirror)
            remote_report = validate_website_mirror(remote, registry=registry)
            report.issues.extend(remote_report.issues)
            local = load_json(local_mirror_path) if local_mirror_path.is_file() else None
            if local is not None:
                if remote.get("mirror", {}).get("source_sha256") != local.get(
                    "mirror", {}
                ).get("source_sha256"):
                    report.add(
                        "WEBSITE_MIRROR_DRIFT",
                        site_mirror.as_posix(),
                        "website mirror hash differs from data website-mirror.json",
                    )
                if remote.get("families") != local.get("families"):
                    report.add(
                        "WEBSITE_MIRROR_DRIFT",
                        site_mirror.as_posix(),
                        "website families differ from data mirror",
                    )
    elif require_website:
        report.add(
            "WEBSITE_ROOT_MISSING",
            "website",
            "website root not found; set ZEROREALM_WEBSITE_ROOT or checkout sibling",
        )

    return report
