"""Simple bug condition exploration test - directly examines the source code.

This script reads the metrics.py file and checks if the callbacks are defined
as async functions, which is the root cause of the bug.

**Property 1: Bug Condition** - Observable Gauge Callbacks Return Coroutines Instead of Observations

**CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists

**Validates: Requirements 2.1, 2.2, 2.3**
"""

import re
from pathlib import Path

def check_callback_is_async(source_code, callback_name):
    """Check if a callback function is defined as async."""
    # Pattern to match: async def callback_name(
    pattern = rf'async\s+def\s+{callback_name}\s*\('
    
    match = re.search(pattern, source_code)
    return match is not None

def extract_callback_definition(source_code, callback_name):
    """Extract the function definition for a callback."""
    # Pattern to match the function definition
    pattern = rf'(async\s+)?def\s+{callback_name}\s*\([^)]*\)'
    
    match = re.search(pattern, source_code)
    if match:
        return match.group(0)
    return None

def main():
    """Run bug condition exploration test."""
    print("="*70)
    print("OpenTelemetry Metrics Bug Condition Exploration Test")
    print("="*70)
    print("\nThis test examines the source code to confirm the bug exists.")
    print("Expected outcome on UNFIXED code: Tests FAIL")
    print("Expected outcome on FIXED code: Tests PASS")
    
    # Read the metrics.py file
    metrics_file = Path(__file__).parent / "open_webui" / "utils" / "telemetry" / "metrics.py"
    
    if not metrics_file.exists():
        print(f"\n❌ ERROR: Cannot find {metrics_file}")
        return 1
    
    print(f"\nReading: {metrics_file}")
    source_code = metrics_file.read_text()
    
    # The three callbacks that should be tested
    callbacks = [
        'observe_total_registered_users',
        'observe_active_users',
        'observe_users_active_today',
    ]
    
    print("\n" + "="*70)
    print("TEST: Check if callbacks are defined as async functions")
    print("="*70)
    
    results = []
    
    for callback_name in callbacks:
        print(f"\n{'='*70}")
        print(f"Checking: {callback_name}")
        print(f"{'='*70}")
        
        # Extract the function definition
        definition = extract_callback_definition(source_code, callback_name)
        
        if definition is None:
            print(f"❌ ERROR: Could not find function definition for {callback_name}")
            results.append((callback_name, None))
            continue
        
        print(f"Definition: {definition}")
        
        # Check if it's async
        is_async = check_callback_is_async(source_code, callback_name)
        
        if is_async:
            print(f"❌ FAIL: {callback_name} is defined as 'async def'")
            print(f"   This is the ROOT CAUSE of the bug!")
            print(f"   OpenTelemetry SDK expects synchronous callbacks.")
            print(f"   When invoked, this will return a coroutine object.")
            print(f"   OTEL will try to iterate over the coroutine, causing:")
            print(f"   TypeError: 'coroutine' object is not iterable")
            results.append((callback_name, False))
        else:
            print(f"✓ PASS: {callback_name} is a synchronous function")
            results.append((callback_name, True))
    
    # Check for await statements in the callbacks
    print("\n" + "="*70)
    print("ADDITIONAL CHECK: Looking for 'await' statements in callbacks")
    print("="*70)
    print("\nOn unfixed code, callbacks use 'await Users.get_*()' which")
    print("requires the callback to be async, causing the bug.")
    
    for callback_name in callbacks:
        # Find the callback function body
        pattern = rf'(async\s+)?def\s+{callback_name}\s*\([^)]*\).*?(?=\n(?:async\s+)?def\s+|\nclass\s+|\Z)'
        match = re.search(pattern, source_code, re.DOTALL)
        
        if match:
            func_body = match.group(0)
            has_await = 'await' in func_body
            
            if has_await:
                print(f"\n{callback_name}:")
                print(f"  Contains 'await' statements: Yes")
                print(f"  This requires the function to be async, causing the bug.")
            else:
                print(f"\n{callback_name}:")
                print(f"  Contains 'await' statements: No")
                print(f"  Good - synchronous implementation.")
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    total_tests = len([r for r in results if r[1] is not None])
    passed_tests = sum(1 for _, passed in results if passed is True)
    failed_tests = sum(1 for _, passed in results if passed is False)
    
    for callback_name, passed in results:
        if passed is None:
            status = "⚠ ERROR"
        elif passed:
            status = "✓ PASS"
        else:
            status = "❌ FAIL"
        print(f"{status}: {callback_name}")
    
    print(f"\nTotal: {total_tests} tests")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    
    if failed_tests > 0:
        print("\n" + "="*70)
        print("CONCLUSION: Bug condition CONFIRMED!")
        print("="*70)
        print("\nCounterexamples found:")
        for callback_name, passed in results:
            if passed is False:
                print(f"  - {callback_name} is defined as 'async def'")
        
        print("\nBug manifestation:")
        print("  When PeriodicExportingMetricReader invokes these callbacks,")
        print("  they return coroutine objects instead of Sequence[Observation].")
        print("  OTEL tries to iterate: for obs in callback(options)")
        print("  This raises: TypeError: 'coroutine' object is not iterable")
        print("  Location: opentelemetry/sdk/metrics/_internal/instrument.py:140")
        
        print("\nRoot cause:")
        print("  The callbacks use 'await Users.get_*()' to call async database")
        print("  methods, which requires the callbacks to be async functions.")
        print("  However, OpenTelemetry SDK expects synchronous callbacks.")
        
        return 1
    else:
        print("\n" + "="*70)
        print("CONCLUSION: Bug is FIXED!")
        print("="*70)
        print("\nAll callbacks are synchronous functions.")
        print("They should return Sequence[Observation] without issues.")
        return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
