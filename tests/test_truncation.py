"""Tests for truncation utilities (truncate_for_llm)."""

from __future__ import annotations

from tools.truncate_for_llm import (
    MAX_STRING_BYTES,
    OVER_LIMIT_TEMPLATE,
    get_tool_truncation_occurred,
    reset_tool_truncation_occurred,
    truncate_string_to_bytes,
    truncate_strings_for_llm,
)


# ---------------------------------------------------------------------------
# truncate_string_to_bytes
# ---------------------------------------------------------------------------

class TestTruncateStringToBytes:
    def test_short_string_unchanged(self):
        assert truncate_string_to_bytes("hello") == "hello"

    def test_long_string_truncated(self):
        long_str = "A" * 5000
        result = truncate_string_to_bytes(long_str, max_bytes=100)
        assert len(result.encode("utf-8")) <= 150  # 100 + suffix + signal overhead

    def test_contains_truncation_marker(self):
        long_str = "B" * 5000
        result = truncate_string_to_bytes(long_str, max_bytes=100)
        assert "..." in result
        assert "truncated" in result

    def test_utf8_multibyte_safe(self):
        # Each emoji is 4 bytes. Truncation should not produce broken UTF-8.
        emoji_str = "\U0001f4a9" * 1000  # 4000 bytes
        result = truncate_string_to_bytes(emoji_str, max_bytes=100)
        # Should be valid UTF-8 (encode/decode without error)
        result.encode("utf-8").decode("utf-8")

    def test_non_string_passthrough(self):
        assert truncate_string_to_bytes(42) == 42
        assert truncate_string_to_bytes(None) is None

    def test_sets_context_var(self):
        reset_tool_truncation_occurred()
        assert get_tool_truncation_occurred() is False
        truncate_string_to_bytes("X" * 5000, max_bytes=100)
        assert get_tool_truncation_occurred() is True

    def test_no_signal_when_disabled(self):
        result = truncate_string_to_bytes("Z" * 5000, max_bytes=100, include_size_signal=False)
        assert "truncated" not in result
        assert "..." in result


# ---------------------------------------------------------------------------
# truncate_strings_for_llm (recursive)
# ---------------------------------------------------------------------------

class TestTruncateStringsForLlm:
    def test_short_dict_unchanged(self):
        obj = {"a": "hello", "b": 42}
        result, truncated = truncate_strings_for_llm(obj)
        assert result == obj
        assert truncated is False

    def test_long_string_in_dict_replaced(self):
        obj = {"data": "X" * 5000}
        result, truncated = truncate_strings_for_llm(obj, max_bytes=100)
        assert truncated is True
        assert "exceeds size limit" in result["data"]

    def test_nested_dict(self):
        obj = {"outer": {"inner": "Y" * 5000}}
        result, truncated = truncate_strings_for_llm(obj, max_bytes=100)
        assert truncated is True
        assert "exceeds size limit" in result["outer"]["inner"]

    def test_list_elements(self):
        obj = ["short", "Z" * 5000]
        result, truncated = truncate_strings_for_llm(obj, max_bytes=100)
        assert truncated is True
        assert result[0] == "short"
        assert "exceeds size limit" in result[1]

    def test_non_string_values_preserved(self):
        obj = {"count": 42, "flag": True, "data": None}
        result, truncated = truncate_strings_for_llm(obj)
        assert result == obj
        assert truncated is False

    def test_mixed_nested_structure(self):
        obj = {
            "posts": [
                {"title": "short", "body": "W" * 5000},
                {"title": "also short", "body": "ok"},
            ],
            "count": 2,
        }
        result, truncated = truncate_strings_for_llm(obj, max_bytes=100)
        assert truncated is True
        assert result["posts"][0]["title"] == "short"
        assert "exceeds size limit" in result["posts"][0]["body"]
        assert result["posts"][1]["body"] == "ok"


# ---------------------------------------------------------------------------
# Context var reset/get cycle
# ---------------------------------------------------------------------------

class TestContextVar:
    def test_reset_clears_flag(self):
        # Force it to True via a truncation
        truncate_string_to_bytes("A" * 5000, max_bytes=100)
        assert get_tool_truncation_occurred() is True
        reset_tool_truncation_occurred()
        assert get_tool_truncation_occurred() is False
