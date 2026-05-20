# AsyncPG Event Loop Issue with OpenTelemetry Metrics

## Problem

The initial fix (creating a new event loop with `asyncio.new_event_loop()` and using `loop.run_until_complete()`) works for SQLite with aiosqlite but **fails with PostgreSQL using asyncpg**.

### Error
```
RuntimeError: Task got Future attached to a different loop
asyncpg.exceptions._base.InternalClientError: got result for unknown protocol state 3
```

### Root Cause
AsyncPG database connections are bound to specific event loops. When we:
1. Create a new event loop in the OTEL worker thread
2. Try to run `Users.get_*()` methods that use existing database connections
3. Those connections are attached to the main FastAPI event loop
4. AsyncPG detects the mismatch and raises RuntimeError

## Current Workaround

The callbacks now return `0` to prevent crashes:
```python
def observe_active_users(options: metrics.CallbackOptions) -> Sequence[metrics.Observation]:
    # Cannot query async database from OTEL worker thread with asyncpg
    return [metrics.Observation(value=0)]
```

**Impact**: User metrics (webui.users.total, webui.users.active, webui.users.active.today) will always report 0.

## Proper Solutions

### Option 1: Remove User Metrics (Simplest)
Remove the three observable gauge metrics entirely. They're not critical for system monitoring.

**Pros**: Clean, no complexity
**Cons**: Lose visibility into user counts

### Option 2: Use Thread-Safe Queue (Recommended)
Have the callbacks return cached values that are updated periodically by a background task running in the main event loop.

```python
# Global cache updated by background task
_user_metrics_cache = {
    'total': 0,
    'active': 0,
    'active_today': 0
}

# Background task in main event loop
async def update_user_metrics_cache():
    while True:
        _user_metrics_cache['total'] = await Users.get_num_users() or 0
        _user_metrics_cache['active'] = await Users.get_active_user_count()
        _user_metrics_cache['active_today'] = await Users.get_num_users_active_today()
        await asyncio.sleep(60)  # Update every minute

# Callbacks read from cache
def observe_total_registered_users(options: metrics.CallbackOptions) -> Sequence[metrics.Observation]:
    return [metrics.Observation(value=_user_metrics_cache['total'])]
```

**Pros**: Works with asyncpg, metrics are eventually consistent
**Cons**: Adds background task, metrics lag by up to 60 seconds

### Option 3: Use asyncio.run_coroutine_threadsafe() (Complex)
Schedule the coroutine on the main event loop from the OTEL worker thread.

```python
def observe_total_registered_users(options: metrics.CallbackOptions) -> Sequence[metrics.Observation]:
    # Get reference to main event loop
    main_loop = asyncio.get_event_loop()  # This needs to be captured at setup time
    
    # Schedule coroutine on main loop and wait for result
    future = asyncio.run_coroutine_threadsafe(Users.get_num_users(), main_loop)
    value = future.result(timeout=5.0)  # Wait up to 5 seconds
    return [metrics.Observation(value=value or 0)]
```

**Pros**: Real-time metrics
**Cons**: Complex, requires capturing main loop reference, can block OTEL thread

### Option 4: Database-Specific Detection
Detect if using asyncpg and disable user metrics automatically.

```python
from open_webui.internal.db import get_db_engine

def observe_total_registered_users(options: metrics.CallbackOptions) -> Sequence[metrics.Observation]:
    engine = get_db_engine()
    if 'asyncpg' in str(engine.url):
        # AsyncPG detected - return 0
        return [metrics.Observation(value=0)]
    
    # Safe to use event loop with aiosqlite
    loop = asyncio.new_event_loop()
    try:
        value = loop.run_until_complete(Users.get_num_users())
        return [metrics.Observation(value=value or 0)]
    finally:
        loop.close()
```

**Pros**: Works for SQLite, gracefully degrades for PostgreSQL
**Cons**: Still no metrics for PostgreSQL users

## Recommendation

**Option 2 (Background Task with Cache)** is the best solution because:
- Works with all database backends (SQLite, PostgreSQL)
- Provides real user metrics (with acceptable lag)
- Clean implementation
- No risk of blocking OTEL thread

## Implementation Status

Currently using **temporary workaround** (returning 0) to prevent crashes.
Proper fix (Option 2) should be implemented in a follow-up.
