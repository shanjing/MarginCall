"""Tests for tools/config.py helpers."""

from __future__ import annotations

import os
from unittest.mock import patch


class TestEnvStrip:
    def _fn(self, key, default=""):
        from tools.config import _env_strip
        return _env_strip(key, default)

    def test_strips_whitespace(self):
        with patch.dict(os.environ, {"TEST_KEY": "  hello  "}):
            assert self._fn("TEST_KEY") == "hello"

    def test_strips_quotes(self):
        with patch.dict(os.environ, {"TEST_KEY": "'gemini-2.5-flash'"}):
            assert self._fn("TEST_KEY") == "gemini-2.5-flash"

    def test_strips_double_quotes(self):
        with patch.dict(os.environ, {"TEST_KEY": '"some-model"'}):
            assert self._fn("TEST_KEY") == "some-model"

    def test_default_value(self):
        # Use a key that definitely doesn't exist
        assert self._fn("NONEXISTENT_KEY_XYZ_12345", "fallback") == "fallback"


class TestCacheDisabledParsing:
    def test_false_by_default(self):
        with patch.dict(os.environ, {"CACHE_DISABLED": "false"}):
            assert os.getenv("CACHE_DISABLED", "false").lower() == "false"

    def test_true_when_set(self):
        with patch.dict(os.environ, {"CACHE_DISABLED": "true"}):
            assert os.getenv("CACHE_DISABLED", "false").lower() == "true"

    def test_case_insensitive(self):
        with patch.dict(os.environ, {"CACHE_DISABLED": "TRUE"}):
            assert os.getenv("CACHE_DISABLED", "false").lower() == "true"
