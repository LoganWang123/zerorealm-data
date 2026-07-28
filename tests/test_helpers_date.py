"""Tests for explicit output-date handling."""

import pytest

from utils.helpers import today_path


def test_today_path_uses_explicit_date():
    assert today_path("2026-08-01") == "2026/08/01"


def test_today_path_rejects_invalid_date():
    with pytest.raises(ValueError):
        today_path("2026/08/01")
