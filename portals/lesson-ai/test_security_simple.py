#!/usr/bin/env python3
"""
Simple security fix verification (no pytest required)
"""

import sys
import time
import os

# Add parent directory to path to import lab_core
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from lab_core import is_stuck, sanitize_run, _safe_regex_match, _safe_regex_search, NONBUILD_RX, STUCK_RX
    print("✓ Successfully imported lab_core with security fixes")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)


# Mock lesson
MOCK_LESSON = {
    "sprites": [
        {"name": "小貓", "costumes": [{"name": "costume1"}]},
    ]
}


def test_redos_protection():
    """Test ReDoS vulnerability is fixed"""
    print("\n=== Testing ReDoS Protection ===")

    # Normal input should work
    assert is_stuck("唔知"), "Normal stuck detection failed"
    print("✓ Normal stuck detection works")

    # Long input should not hang
    malicious = "係" * 1000 + "x"
    start = time.time()
    result = is_stuck(malicious)
    duration = time.time() - start

    if duration < 0.1:
        print(f"✓ ReDoS protection working ({duration:.4f}s for {len(malicious)} char input)")
    else:
        print(f"✗ POTENTIAL ReDoS: took {duration:.2f}s")
        return False

    assert result is False
    return True


def test_json_depth_protection():
    """Test JSON depth vulnerability is fixed"""
    print("\n=== Testing JSON Depth Protection ===")

    # Normal input should work
    run = {
        "secs": 1.5,
        "sprites": {"小貓": {"start": [0, 0]}},
    }
    result = sanitize_run(run, MOCK_LESSON)
    assert result is not None, "Normal run sanitization failed"
    print("✓ Normal run sanitization works")

    # Deeply nested should be rejected
    nested = {}
    current = nested
    for i in range(20):
        current["nested"] = {}
        current = current["nested"]

    run_malicious = {"secs": 1.5, "sprites": nested}
    result = sanitize_run(run_malicious, MOCK_LESSON)

    if result is None:
        print("✓ Deeply nested JSON rejected (depth protection working)")
    else:
        print("✗ WARNING: Deeply nested JSON accepted")
        return False

    return True


def test_inflight_fix():
    """Test _inflight race condition fix"""
    print("\n=== Testing _inflight Race Condition Fix ===")

    # Read source to verify fix is present
    with open(__file__.replace("test_security_simple.py", "lab_core.py")) as f:
        source = f.read()

    if "_inflight.get(u, 0) - 1" in source:
        print("✓ _inflight race condition FIXED (using get(u, 0))")
    else:
        print("✗ WARNING: _inflight fix not found")
        return False

    if "_inflight.get(u, 1) - 1" in source:
        print("✗ BUG PRESENT: old buggy code still exists")
        return False

    return True


def test_large_number_validation():
    """Test large number validation"""
    print("\n=== Testing Large Number Validation ===")

    from lab_core import _num

    class MockCtx:
        def __init__(self):
            self.errors = []
            self.names = set()

        def err(self, msg):
            self.errors.append(msg)

    ctx = MockCtx()

    # Normal number should work
    result = _num("10", ctx, "motion_movesteps", "STEPS")
    assert result == 10
    print("✓ Normal number validation works")

    # Very large string should be rejected quickly
    ctx = MockCtx()
    malicious = "1" + "0" * 200

    start = time.time()
    result = _num(malicious, ctx, "motion_movesteps", "STEPS")
    duration = time.time() - start

    if duration < 0.01:
        print(f"✓ Large number rejected quickly ({duration:.6f}s)")
    else:
        print(f"✗ WARNING: Large number took {duration:.4f}s")

    assert result == 0
    assert len(ctx.errors) > 0
    print("✓ Large number validation working")

    return True


def test_safe_regex_wrappers():
    """Test safe regex wrapper functions"""
    print("\n=== Testing Safe Regex Wrappers ===")

    # Normal input should work
    assert _safe_regex_match(NONBUILD_RX, "係") is True
    print("✓ _safe_regex_match works for normal input")

    # Long input should be rejected
    long_text = "a" * 1000
    result = _safe_regex_match(NONBUILD_RX, long_text, default=False)
    assert result is False
    print("✓ _safe_regex_match rejects long input")

    result = _safe_regex_search(STUCK_RX, long_text, default=False)
    assert result is False
    print("✓ _safe_regex_search rejects long input")

    return True


def main():
    print("=" * 60)
    print("Wonder Lab Studio - Security Fix Verification")
    print("=" * 60)

    tests = [
        test_redos_protection,
        test_json_depth_protection,
        test_inflight_fix,
        test_large_number_validation,
        test_safe_regex_wrappers,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} raised exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\n🎉 All security fixes verified!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
