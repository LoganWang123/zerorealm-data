"""Tests for processors/dedup.py — deduplication logic."""

import os
import json
import tempfile

import pytest

from crawlers.base import RawItem
from processors.dedup import is_duplicate, filter_duplicates


def _make_item(item_id: str, source: str = "test", title: str = "title") -> RawItem:
    return RawItem(
        id=item_id,
        source=source,
        source_type="rss",
        language="zh-CN",
        title=title,
        url=f"https://example.com/{item_id}",
        published_at="2026-07-26T08:00:00+08:00",
        crawled_at="2026-07-26T09:00:00+08:00",
        run_id="test",
        crawl_status="success",
        http_status=200,
        content_html="",
        content_text="content",
        summary="summary",
        author="",
        metadata={},
    )


class TestIsDuplicate:
    def test_no_data_dir(self, tmp_path):
        item = _make_item("abc")
        assert is_duplicate(item, str(tmp_path / "nonexistent")) is False

    def test_existing_file_is_duplicate(self, tmp_path):
        item = _make_item("abc", source="36kr")
        # Create matching file: data/raw/2026/07/26/36kr_abc.json
        raw_dir = tmp_path / "raw" / "2026" / "07" / "26"
        raw_dir.mkdir(parents=True)
        (raw_dir / "36kr_abc.json").write_text("{}", encoding="utf-8")

        assert is_duplicate(item, str(tmp_path)) is True

    def test_new_item_not_duplicate(self, tmp_path):
        item = _make_item("xyz", source="36kr")
        raw_dir = tmp_path / "raw" / "2026" / "07" / "26"
        raw_dir.mkdir(parents=True)
        (raw_dir / "36kr_abc.json").write_text("{}", encoding="utf-8")

        assert is_duplicate(item, str(tmp_path)) is False


class TestFilterDuplicates:
    def test_in_batch_dedup(self, tmp_path):
        items = [
            _make_item("aaa", title="first"),
            _make_item("aaa", title="duplicate"),
            _make_item("bbb", title="unique"),
        ]
        new_items, dup_count = filter_duplicates(items, str(tmp_path))
        assert len(new_items) == 2
        assert dup_count == 1
        assert new_items[0].title == "first"

    def test_all_unique(self, tmp_path):
        items = [_make_item("a"), _make_item("b"), _make_item("c")]
        new_items, dup_count = filter_duplicates(items, str(tmp_path))
        assert len(new_items) == 3
        assert dup_count == 0

    def test_all_duplicates(self, tmp_path):
        items = [_make_item("same"), _make_item("same"), _make_item("same")]
        new_items, dup_count = filter_duplicates(items, str(tmp_path))
        assert len(new_items) == 1
        assert dup_count == 2

    def test_empty_input(self, tmp_path):
        new_items, dup_count = filter_duplicates([], str(tmp_path))
        assert new_items == []
        assert dup_count == 0
