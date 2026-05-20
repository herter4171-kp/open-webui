"""Standalone bug condition exploration test for OpenTelemetry metrics callbacks.

This script directly tests the three observable gauge callbacks to demonstrate
the bug exists on unfixed code.

**Property 1: Bug Condition** - Observable Gauge Callbacks Return Coroutines Instead of Observations

**CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists

**Validates: Requirements 2.1, 2.2, 2.3**

Expected behavior:
- Callbacks should return Sequence[Observation] synchronously
- Callbacks should NOT return coroutine objects
- Callbacks should be iterable without raising TypeError

On UNFIXED code: Test FAILS with TypeError or assertion errors
On FIXED code: Test PASSES confirming expected behavior
"""

import inspect
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

# Import the metrics module directly
from open_webui.utils.telemetry import metrics as metrics_module

def test_callback_is_not_coroutine_function(callback_name, callback_func):
    """Test that a callback is not a coroutine function (not async def)."""
    print(f"\n{'='*70}")
    print(f"Testing: {callback_name}")
    print(f"{'='*70}")
    
    is_coroutine_func = inspect.iscoroutinefunction(callback_func)
    print(f"Is coroutine function (async def): {is_coroutine_func}")
    
    if is_coroutine_func:
        print(f"❌ FAIL: {callback_name} is defined as 'async def'")
        print(f"   This is the ROOT CAUSE of the bug!")
        print(f"   OpenTelemetry SDK requires synchronous callbacks.")
        return False
    else:
        print(f"✓ PASS: {callback_name} is a synchronous function")
        return True

def test_callback_returns_observations_not_coroutine(callback_name, callback_func):
    """Test that invoking a callback returns Sequence[Observation], not a coroutine."""
    print(f"\nInvoking {callback_name}...")
    
    # Create a mock CallbackOptions (it's not used by the callbacks)
    class MockCallbackOptions:
        pass
    
    mock_options = MockCallbackOptions()
    
    try:
        result = callback_func(mock_options)
    except Exception as e:
        print(f"❌ FAIL: Exception when invoking callback: {e}")
        return False
    
    print(f"Result type: {type(result)}")
    print(f"Result value: {result}")
    
    # Check if result is a coroutine
    is_coroutine = inspect.iscoroutine(result)
    print(f"Is coroutine object: {is_coroutine}")
    
    if is_coroutine:
        print(f"❌ FAIL: {callback_name} returned a coroutine object")
        print(f"   This is the BUG CONDITION!")
        print(f"   OpenTelemetry SDK expects Sequence[Observation], not a coroutine")
        print(f"   When OTEL tries to iterate over this, it will raise:")
        print(f"   TypeError: 'coroutine' object is not iterable")
        
        # Clean up the coroutine
        result.close()
        return False
    
    # Try to iterate over the result
    print(f"Attempting to iterate over result...")
    try:
        observations = list(result)
        print(f"✓ Successfully iterated, got {len(observations)} observation(s)")
        
        # Check each observation
        for i, obs in enumerate(observations):
            print(f"  Observation {i}: type={type(obs)}, value={getattr(obs, 'value', 'N/A')}")
        
        return True
    except TypeError as e:
        print(f"❌ FAIL: Cannot iterate over result: {e}")
        print(f"   This is the BUG MANIFESTATION!")
        print(f"   OpenTelemetry SDK fails at this point with TypeError")
        return False

def main():
    """Run bug condition exploration tests."""
    print("="*70)
    print("OpenTelemetry Metrics Bug Condition Exploration Test")
    print("="*70)
    print("\nThis test demonstrates the bug on UNFIXED code.")
    print("Expected outcome: Tests FAIL, confirming the bug exists.")
    print("\nAfter the fix is applied, these tests should PASS.")
    
    # Get the three callbacks
    callbacks = [
        ('observe_total_registered_users', metrics_module.observe_total_registered_users),
        ('observe_active_users', metrics_module.observe_active_users),
        ('observe_users_active_today', metrics_module.observe_users_active_today),
    ]
    
    results = []
    
    # Test 1: Check if callbacks are coroutine functions
    print("\n" + "="*70)
    print("TEST 1: Check if callbacks are coroutine functions (async def)")
    print("="*70)
    
    for name, callback in callbacks:
        passed = test_callback_is_not_coroutine_function(name, callback)
        results.append((f"{name} - not async def", passed))
    
    # Test 2: Check if invoking callbacks returns coroutines
    print("\n" + "="*70)
    print("TEST 2: Check if invoking callbacks returns coroutines")
    print("="*70)
    print("\nNOTE: This test will attempt to invoke the callbacks.")
    print("On unfixed code, this will return coroutine objects.")
    print("We cannot actually await them here without a database connection.")
    
    for name, callback in callbacks:
        passed = test_callback_returns_observations_not_coroutine(name, callback)
        results.append((f"{name} - returns observations", passed))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)
    failed_tests = total_tests - passed_tests
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {total_tests} tests")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    
    if failed_tests > 0:
        print("\n" + "="*70)
        print("CONCLUSION: Bug condition confirmed!")
        print("="*70)
        print("\nThe callbacks are async functions that return coroutines.")
        print("OpenTelemetry SDK expects synchronous callbacks that return")
        print("Sequence[Observation] objects.")
        print("\nThis causes: TypeError: 'coroutine' object is not iterable")
        print("Location: opentelemetry/sdk/metrics/_internal/instrument.py:140")
        print("\nCounterexamples documented:")
        for test_name, passed in results:
            if not passed:
                print(f"  - {test_name}")
        return 1
    else:
        print("\n" + "="*70)
        print("CONCLUSION: Bug is FIXED!")
        print("="*70)
        print("\nAll callbacks are synchronous and return Sequence[Observation].")
        return 0

if __name__ == "__main__":
    sys.exit(main())
