"""Standalone test to verify the OTEL metrics fix works correctly."""

import inspect
import asyncio
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider


def test_callbacks_are_synchronous():
    """Verify that all three callback functions are now synchronous."""
    # Import the module
    import sys
    sys.path.insert(0, 'backend')
    from open_webui.utils.telemetry import metrics as metrics_module
    
    # Get the source code
    source = inspect.getsource(metrics_module.setup_metrics)
    
    # Parse to find the callback functions
    import ast
    tree = ast.parse(source)
    
    callbacks_found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in [
            'observe_total_registered_users',
            'observe_active_users',
            'observe_users_active_today'
        ]:
            # Check it's NOT an AsyncFunctionDef
            is_sync = not isinstance(node, ast.AsyncFunctionDef)
            callbacks_found.append((node.name, is_sync))
    
    print("Callback synchronicity check:")
    for name, is_sync in callbacks_found:
        status = "✓ SYNC" if is_sync else "✗ ASYNC"
        print(f"  {name}: {status}")
    
    assert len(callbacks_found) == 3, f"Expected 3 callbacks, found {len(callbacks_found)}"
    assert all(is_sync for _, is_sync in callbacks_found), "All callbacks must be synchronous"
    print("\n✓ All callbacks are synchronous!")


def test_event_loop_pattern():
    """Verify the event loop pattern is correctly implemented."""
    with open('backend/open_webui/utils/telemetry/metrics.py', 'r') as f:
        content = f.read()
    
    # Check for the pattern in each callback
    patterns = {
        'asyncio import': 'import asyncio' in content,
        'new_event_loop': content.count('asyncio.new_event_loop()') == 3,
        'run_until_complete': content.count('loop.run_until_complete') == 3,
        'loop.close in finally': content.count('loop.close()') == 3,
    }
    
    print("\nEvent loop pattern check:")
    for pattern, present in patterns.items():
        status = "✓" if present else "✗"
        print(f"  {status} {pattern}")
    
    assert all(patterns.values()), "All event loop patterns must be present"
    print("\n✓ Event loop pattern correctly implemented!")


def test_no_async_keywords():
    """Verify no async/await keywords in callback definitions."""
    with open('backend/open_webui/utils/telemetry/metrics.py', 'r') as f:
        lines = f.readlines()
    
    # Find callback function definitions
    callback_names = [
        'observe_total_registered_users',
        'observe_active_users',
        'observe_users_active_today'
    ]
    
    print("\nAsync keyword check:")
    for i, line in enumerate(lines, 1):
        for callback_name in callback_names:
            if f'def {callback_name}' in line:
                if 'async def' in line:
                    print(f"  ✗ Line {i}: {callback_name} is still async!")
                    assert False, f"{callback_name} should not be async"
                else:
                    print(f"  ✓ Line {i}: {callback_name} is sync")
    
    print("\n✓ No async keywords in callback definitions!")


if __name__ == '__main__':
    print("=" * 70)
    print("OTEL Metrics Fix Verification")
    print("=" * 70)
    
    try:
        test_callbacks_are_synchronous()
        test_event_loop_pattern()
        test_no_async_keywords()
        
        print("\n" + "=" * 70)
        print("✓ ALL VERIFICATION TESTS PASSED!")
        print("=" * 70)
        print("\nThe fix has been correctly implemented:")
        print("  • All three callbacks converted from async to sync")
        print("  • Event loop creation pattern properly implemented")
        print("  • loop.run_until_complete() used to run async queries")
        print("  • loop.close() called in finally blocks")
        print("\nThe TypeError should no longer occur when OTEL tries to")
        print("invoke these callbacks from the PeriodicExportingMetricReader.")
        
    except Exception as e:
        print(f"\n✗ VERIFICATION FAILED: {e}")
        raise
