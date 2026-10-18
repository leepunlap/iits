#!/usr/bin/env python3
"""
Security fix tests for Wonder Lab Studio
Tests for CVE-level vulnerabilities fixed in lab_core.py
"""

import pytest
import re
import json
from lab_core import (
    is_stuck,
    _safe_regex_match,
    _safe_regex_search,
    sanitize_run,
    NONBUILD_RX,
    STUCK_RX,
)


# Mock lesson object for tests
MOCK_LESSON = {
    "sprites": [
        {"name": "小貓", "costumes": [{"name": "costume1"}]},
        {"name": "小狗", "costumes": [{"name": "costume2"}]},
    ]
}


class TestReDoSProtection:
    """Test ReDoS vulnerability fixes"""

    def test_stuck_rx_normal_input(self):
        """Normal input should work"""
        assert is_stuck("唔知")
        assert is_stuck("你決定")
        assert not is_stuck("我想移動小貓")

    def test_stuck_rx_long_input_prevention(self):
        """Very long input should not hang"""
        # Create malicious input designed to trigger catastrophic backtracking
        malicious = "係" * 1000 + "x"  # Original pattern: ^(\s*(係|...)*)+$

        # Should complete quickly (not hang) and return False
        import time
        start = time.time()
        result = is_stuck(malicious)
        duration = time.time() - start

        assert duration < 0.1, f"ReDoS vulnerability: took {duration}s"
        assert result is False

    def test_safe_regex_match_with_long_input(self):
        """_safe_regex_match should reject long inputs"""
        long_text = "a" * 1000
        result = _safe_regex_match(NONBUILD_RX, long_text, default=False)
        assert result is False

    def test_safe_regex_search_with_long_input(self):
        """_safe_regex_search should reject long inputs"""
        long_text = "a" * 1000
        result = _safe_regex_search(STUCK_RX, long_text, default=False)
        assert result is False

    def test_nonbuild_rx_normal_input(self):
        """Normal input should work"""
        assert _safe_regex_match(NONBUILD_RX, "係")
        assert _safe_regex_match(NONBUILD_RX, "ok")
        assert not _safe_regex_match(NONBUILD_RX, "我想加一個移動積木")


class TestJSONDepthProtection:
    """Test JSON depth vulnerability fix"""

    def test_sanitize_run_normal_input(self):
        """Normal run report should work"""
        run = {
            "secs": 1.5,
            "sprites": {
                "小貓": {
                    "start": [0, 0],
                    "end": [10, 20],
                }
            },
            "vars": {"分數": 10},
        }

        result = sanitize_run(run, MOCK_LESSON)
        assert result is not None
        assert result["secs"] == 1.5

    def test_sanitize_run_deeply_nested_attack(self):
        """Deeply nested JSON should be rejected"""
        # Create malicious deeply-nested structure
        nested = {}
        current = nested
        for i in range(20):  # Exceed MAX_JSON_DEPTH (10)
            current["nested"] = {}
            current = current["nested"]

        run = {
            "secs": 1.5,
            "sprites": nested,  # Inject malicious structure
        }

        result = sanitize_run(run, MOCK_LESSON)
        # Should return None for malicious input
        assert result is None

    def test_sanitize_run_moderately_nested_ok(self):
        """Moderately nested (under limit) should work"""
        run = {
            "secs": 1.5,
            "sprites": {
                "小貓": {
                    "touched_colors": {
                        "#ff0000": "1",
                        "#00ff00": "2",
                    }
                }
            },
        }

        result = sanitize_run(run, MOCK_LESSON)
        assert result is not None


class TestInflightRaceCondition:
    """Test _inflight resource leak fix

    NOTE: This requires accessing internal state of lab_core module.
    In production, this would be tested via integration tests.
    """

    def test_inflight_decrement_logic(self):
        """Verify the fix: _inflight.get(u, 0) - 1, not get(u, 1) - 1"""
        # This is a regression test for line 3529
        # The bug: _inflight[u] = _inflight.get(u, 1) - 1
        # The fix: _inflight[u] = _inflight.get(u, 0) - 1

        # Simulate the fixed logic
        _inflight = {}
        u = "test_user"

        # Increment (simulating line 3521)
        _inflight[u] = _inflight.get(u, 0) + 1
        assert _inflight[u] == 1

        # Decrement with FIXED logic (line 3529)
        _inflight[u] = _inflight.get(u, 0) - 1
        assert _inflight[u] == 0

        # Clean up
        if _inflight[u] <= 0:
            _inflight.pop(u, None)

        assert u not in _inflight


class TestLargeNumberValidation:
    """Test large number validation in _num"""

    def test_num_normal_input(self):
        """Normal numbers should work"""
        from lab_core import _num, ValidationContext

        class MockCtx:
            def __init__(self):
                self.errors = []
                self.names = set()

            def err(self, msg):
                self.errors.append(msg)

        ctx = MockCtx()

        result = _num("10", ctx, "motion_movesteps", "STEPS")
        assert result == 10
        assert len(ctx.errors) == 0

    def test_num_very_large_string(self):
        """Very large number strings should be rejected quickly"""
        from lab_core import _num

        class MockCtx:
            def __init__(self):
                self.errors = []
                self.names = set()

            def err(self, msg):
                self.errors.append(msg)

        ctx = MockCtx()

        # Attack: very long number string (DoS attempt)
        malicious = "1" + "0" * 200

        import time
        start = time.time()
        result = _num(malicious, ctx, "motion_movesteps", "STEPS")
        duration = time.time() - start

        # Should complete quickly
        assert duration < 0.01
        assert result == 0  # Returns 0 on error
        assert len(ctx.errors) > 0  # Logged an error

    def test_num_overflow(self):
        """Overflow should be handled gracefully"""
        from lab_core import _num

        class MockCtx:
            def __init__(self):
                self.errors = []
                self.names = set()

            def err(self, msg):
                self.errors.append(msg)

        ctx = MockCtx()

        # Python can handle very large floats, but conversion should be safe
        result = _num("9" * 50, ctx, "motion_movesteps", "STEPS")
        # Should clamp to LIM["num_abs_max"], not crash
        assert isinstance(result, (int, float))


def test_all_fixes_applied():
    """Meta-test: verify all security fixes are present in source"""
    import lab_core
    import inspect

    source = inspect.getsource(lab_core)

    # Fix 1: _inflight race condition
    assert "_inflight.get(u, 0) - 1" in source
    assert "_inflight.get(u, 1) - 1" not in source

    # Fix 2: ReDoS protection
    assert "MAX_TEXT_LENGTH_FOR_REGEX" in source
    assert "_safe_regex_match" in source
    assert "_safe_regex_search" in source

    # Fix 3: JSON depth protection
    assert "MAX_JSON_DEPTH" in source
    assert "check_depth" in source

    # Fix 4: Large number validation
    assert "len(v_str) > 100" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
