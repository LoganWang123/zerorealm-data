"""Tests for local daily pipeline CLI sync/push flags."""

from __future__ import annotations

from run_daily import build_parser, should_push_website


def test_default_does_not_push_website():
    args = build_parser().parse_args([])
    assert should_push_website(args) is False


def test_push_website_flag_enables_push():
    args = build_parser().parse_args(["--push-website"])
    assert should_push_website(args) is True


def test_no_push_remains_supported_and_blocks_push():
    args = build_parser().parse_args(["--push-website", "--no-push"])
    assert should_push_website(args) is False


def test_no_push_alone_keeps_default_off():
    args = build_parser().parse_args(["--no-push"])
    assert should_push_website(args) is False
