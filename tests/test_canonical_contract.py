"""Tests for cross-channel canonical content contract."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from content.canonical_contract import (
    build_website_mirror,
    check_all,
    load_registry,
    validate_packet_against_family,
    validate_packets,
    validate_registry,
    validate_website_mirror,
    ContractReport,
)

ROOT = Path(__file__).resolve().parents[1]


def _family(registry: dict, canonical_id: str) -> dict:
    for family in registry["families"]:
        if family["canonical_id"] == canonical_id:
            return family
    raise KeyError(canonical_id)


def _resolve_website_root_for_tests() -> Path | None:
    candidates = [
        ROOT.parent / "zerorealm-website",
        ROOT / ".ci" / "zerorealm-website",
    ]
    for candidate in candidates:
        if (candidate / "data" / "content-canonical.json").is_file():
            return candidate
    return None


def test_registry_and_packets_pass_in_repo():
    report = check_all(root=ROOT, website_root=_resolve_website_root_for_tests())
    assert report.ok, "\n".join(i.format() for i in report.issues)


def test_version_mismatch_fails():
    registry = load_registry()
    family = _family(registry, "smart-cabinet-stockout-triage")
    packet = {
        "canonical_id": family["canonical_id"],
        "canonical_version": family["canonical_version"] + 1,
        "channel": "wechat",
        "contract": {
            "core_conclusion": family["core_conclusion"],
            "scope_guard": family["evidence"]["scope_guard"],
            "evidence_sources": family["evidence"]["sources"],
        },
        "cta": {
            "copy": family["cta"]["allowed_copy_by_channel"]["wechat"][0],
            "tool_page": family["cta"]["target"]["tool_page"],
            "campaign": family["cta"]["target"]["campaign"],
        },
    }
    report = ContractReport()
    validate_packet_against_family(packet, family, path="tmp.json", report=report)
    assert any(i.code == "VERSION_MISMATCH" for i in report.issues)


def test_core_conclusion_drift_fails():
    registry = load_registry()
    family = _family(registry, "smart-cabinet-five-process-metrics")
    packet = {
        "canonical_id": family["canonical_id"],
        "canonical_version": family["canonical_version"],
        "channel": "zhihu",
        "contract": {
            "core_conclusion": "GMV 才是唯一该盯的指标",
            "scope_guard": family["evidence"]["scope_guard"],
            "evidence_sources": family["evidence"]["sources"],
        },
        "cta": {
            "copy": family["cta"]["allowed_copy_by_channel"]["zhihu"][0],
            "tool_page": family["cta"]["target"]["tool_page"],
            "campaign": family["cta"]["target"]["campaign"],
        },
    }
    report = ContractReport()
    validate_packet_against_family(packet, family, path="tmp.json", report=report)
    assert any(i.code == "CORE_CONCLUSION_DRIFT" for i in report.issues)


def test_scope_and_evidence_drift_fails():
    registry = load_registry()
    family = _family(registry, "smart-cabinet-stockout-triage")
    packet = {
        "canonical_id": family["canonical_id"],
        "canonical_version": family["canonical_version"],
        "channel": "wechat",
        "contract": {
            "core_conclusion": family["core_conclusion"],
            "scope_guard": "适用于所有智能柜补货场景",
            "evidence_sources": [{"type": "invented", "note": "fake"}],
        },
        "cta": {
            "copy": family["cta"]["allowed_copy_by_channel"]["wechat"][0],
            "tool_page": family["cta"]["target"]["tool_page"],
            "campaign": family["cta"]["target"]["campaign"],
        },
    }
    report = ContractReport()
    validate_packet_against_family(packet, family, path="tmp.json", report=report)
    codes = {i.code for i in report.issues}
    assert "SCOPE_GUARD_DRIFT" in codes
    assert "EVIDENCE_SOURCE_DRIFT" in codes


def test_cta_target_drift_fails():
    registry = load_registry()
    family = _family(registry, "smart-cabinet-five-process-metrics")
    packet = {
        "canonical_id": family["canonical_id"],
        "canonical_version": family["canonical_version"],
        "channel": "zhihu",
        "contract": {
            "core_conclusion": family["core_conclusion"],
            "scope_guard": family["evidence"]["scope_guard"],
            "evidence_sources": family["evidence"]["sources"],
        },
        "cta": {
            "copy": family["cta"]["allowed_copy_by_channel"]["zhihu"][0],
            "tool_page": "https://example.com/wrong-tool",
            "campaign": "other_campaign",
        },
    }
    report = ContractReport()
    validate_packet_against_family(packet, family, path="tmp.json", report=report)
    assert any(i.code == "CTA_TARGET_DRIFT" for i in report.issues)


def test_missing_canonical_ref_on_packet(tmp_path: Path):
    registry = load_registry()
    growth = tmp_path / "data" / "growth"
    growth.mkdir(parents=True)
    bad = {
        "piece_id": "tmp-packet",
        "channel": "wechat",
        "title": "no canonical",
    }
    (growth / "content-packet-tmp-2026-08-15.json").write_text(
        json.dumps(bad, ensure_ascii=False),
        encoding="utf-8",
    )
    # Copy registry layout expected by helpers that use ROOT — call validate_packets
    # with tmp root after placing a minimal registry.
    canon = tmp_path / "data" / "content-canonical"
    canon.mkdir(parents=True)
    (canon / "registry.json").write_text(
        json.dumps(registry, ensure_ascii=False),
        encoding="utf-8",
    )
    report = validate_packets(registry, root=tmp_path)
    assert any(i.code == "MISSING_CANONICAL_REF" for i in report.issues)


def test_missing_channel_ref_when_family_lists_absent_packet():
    registry = copy.deepcopy(load_registry())
    family = _family(registry, "smart-cabinet-five-process-metrics")
    family["channels"]["wechat"] = {
        "status": "draft",
        "refs": [
            {
                "kind": "content_packet",
                "path": "data/growth/content-packet-does-not-exist.json",
                "repo": "zerorealm-data",
            }
        ],
    }
    report = validate_packets(registry, root=ROOT)
    assert any(i.code == "MISSING_CHANNEL_REF" for i in report.issues)


def test_mirror_hash_detects_drift():
    registry = load_registry()
    mirror = build_website_mirror(registry)
    assert validate_website_mirror(mirror, registry=registry).ok
    broken = copy.deepcopy(mirror)
    broken["mirror"]["source_sha256"] = "0" * 64
    report = validate_website_mirror(broken, registry=registry)
    assert any(i.code == "MIRROR_HASH_DRIFT" for i in report.issues)


def test_validate_registry_shape():
    assert validate_registry().ok
