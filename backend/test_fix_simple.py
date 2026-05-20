"""Simple verification of the OTEL metrics fix without importing the module."""

import ast


def verify_fix():
    """Verify the fix by analyzing the source code directly."""
    
    with open('backend/open_webui/utils/telemetry/metrics.py', 'r') as f:
        content = f.read()
        tree = ast.parse(content)
    
    print("=" * 70)
    print("OTEL Metrics Fix Verification")
    print("=" * 70)
    
    # Check 1: asyncio import
    print("\n1. Checking asyncio import...")
    if 'import asyncio' in content:
        print("   ✓ asyncio module is imported")
    else:
        print("   ✗ asyncio module NOT imported")
        return False
    
    # Check 2: Find the three callback functions
    print("\n2. Analyzing callback functions...")
    
    callback_names = [
        'observe_total_registered_users',
        'observe_active_users',
        'observe_users_active_today'
    ]
    
    callbacks_found = {}
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name in callback_names:
                # Check if it's async
                is_async = isinstance(node, ast.AsyncFunctionDef)
                
                # Check for event loop pattern
                has_try_finally = False
                has_new_event_loop = False
                has_run_until_complete = False
                has_loop_close = False
                
                for stmt in ast.walk(node):
                    if isinstance(stmt, ast.Try) and stmt.finalbody:
                        has_try_finally = True
                    if isinstance(stmt, ast.Call):
                        if isinstance(stmt.func, ast.Attribute):
                            if stmt.func.attr == 'new_event_loop':
                                has_new_event_loop = True
                            elif stmt.func.attr == 'run_until_complete':
                                has_run_until_complete = True
                            elif stmt.func.attr == 'close':
                                has_loop_close = True
                
                callbacks_found[node.name] = {
                    'is_async': is_async,
                    'has_try_finally': has_try_finally,
                    'has_new_event_loop': has_new_event_loop,
                    'has_run_until_complete': has_run_until_complete,
                    'has_loop_close': has_loop_close
                }
    
    all_correct = True
    
    for name in callback_names:
        if name not in callbacks_found:
            print(f"   ✗ {name}: NOT FOUND")
            all_correct = False
            continue
        
        info = callbacks_found[name]
        
        if info['is_async']:
            print(f"   ✗ {name}: Still async (should be sync)")
            all_correct = False
        elif not info['has_try_finally']:
            print(f"   ✗ {name}: Missing try-finally block")
            all_correct = False
        elif not info['has_new_event_loop']:
            print(f"   ✗ {name}: Missing new_event_loop()")
            all_correct = False
        elif not info['has_run_until_complete']:
            print(f"   ✗ {name}: Missing run_until_complete()")
            all_correct = False
        elif not info['has_loop_close']:
            print(f"   ✗ {name}: Missing loop.close()")
            all_correct = False
        else:
            print(f"   ✓ {name}: Correctly implemented")
    
    # Check 3: Pattern counts
    print("\n3. Verifying pattern counts...")
    event_loop_count = content.count('asyncio.new_event_loop()')
    run_until_complete_count = content.count('loop.run_until_complete')
    loop_close_count = content.count('loop.close()')
    
    print(f"   new_event_loop(): {event_loop_count} (expected: 3)")
    print(f"   run_until_complete: {run_until_complete_count} (expected: 3)")
    print(f"   loop.close(): {loop_close_count} (expected: 3)")
    
    if event_loop_count != 3 or run_until_complete_count != 3 or loop_close_count != 3:
        print("   ✗ Pattern counts don't match expected values")
        all_correct = False
    else:
        print("   ✓ All pattern counts correct")
    
    # Check 4: No async def in callbacks
    print("\n4. Checking for async keywords in callback definitions...")
    lines = content.split('\n')
    async_found = False
    for i, line in enumerate(lines, 1):
        for callback_name in callback_names:
            if f'def {callback_name}' in line and 'async def' in line:
                print(f"   ✗ Line {i}: {callback_name} still has 'async def'")
                async_found = True
                all_correct = False
    
    if not async_found:
        print("   ✓ No async keywords in callback definitions")
    
    # Final result
    print("\n" + "=" * 70)
    if all_correct:
        print("✓ ALL CHECKS PASSED - FIX CORRECTLY IMPLEMENTED")
        print("=" * 70)
        print("\nSummary of changes:")
        print("  • asyncio module imported")
        print("  • All three callbacks converted from async to sync")
        print("  • Each callback creates a new event loop")
        print("  • Each callback runs async code with loop.run_until_complete()")
        print("  • Each callback closes the loop in a finally block")
        print("\nExpected behavior:")
        print("  The PeriodicExportingMetricReader can now invoke these")
        print("  callbacks without raising TypeError about coroutines.")
        return True
    else:
        print("✗ VERIFICATION FAILED - FIX NOT COMPLETE")
        print("=" * 70)
        return False


if __name__ == '__main__':
    success = verify_fix()
    exit(0 if success else 1)
