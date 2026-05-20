"""Tests for OpenTelemetry metrics observable gauge callbacks.

This test module validates the bug condition and preservation properties
for the OpenTelemetry metrics callbacks bugfix.

Bug Context:
- Three observable gauge callbacks are async functions but OpenTelemetry expects sync
- This causes TypeError: 'coroutine' object is not iterable
- The fix converts callbacks to sync functions using event loop pattern
"""

import inspect
import pytest
from typing import Sequence
from unittest.mock import AsyncMock, MagicMock, patch

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource


# Import the module under test
# We need to import after mocking to avoid initialization issues
@pytest.fixture
def mock_users_model():
    """Mock the Users model to avoid database dependencies."""
    with patch('open_webui.utils.telemetry.metrics.Users') as mock_users:
        # Mock the async methods to return test values
        mock_users.get_num_users = AsyncMock(return_value=100)
        mock_users.get_active_user_count = AsyncMock(return_value=50)
        mock_users.get_num_users_active_today = AsyncMock(return_value=25)
        yield mock_users


@pytest.fixture
def mock_meter_provider():
    """Create a mock MeterProvider to avoid OTLP exporter dependencies."""
    resource = Resource.create({"service.name": "test-webui"})
    provider = MeterProvider(resource=resource)
    metrics.set_meter_provider(provider)
    return provider


class TestBugConditionExploration:
    """Task 1: Bug Condition Exploration Test
    
    **Property 1: Bug Condition** - Observable Gauge Callbacks Return Coroutines Instead of Observations
    
    **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
    **DO NOT attempt to fix the test or the code when it fails**
    
    **Validates: Requirements 2.1, 2.2, 2.3**
    
    This test encodes the expected behavior:
    - Callbacks should return Sequence[Observation] synchronously
    - Callbacks should NOT return coroutine objects
    - Callbacks should be iterable without raising TypeError
    
    On UNFIXED code: Test FAILS with TypeError or assertion errors
    On FIXED code: Test PASSES confirming expected behavior
    """
    
    def test_observe_total_registered_users_returns_observations_not_coroutine(
        self, mock_users_model, mock_meter_provider
    ):
        """Test that observe_total_registered_users returns Sequence[Observation], not a coroutine.
        
        **Validates: Requirements 2.1, 2.2, 2.3**
        
        EXPECTED ON UNFIXED CODE: FAIL
        - Result is a coroutine object
        - Attempting to iterate raises TypeError: 'coroutine' object is not iterable
        
        EXPECTED ON FIXED CODE: PASS
        - Result is a Sequence[Observation]
        - Can iterate over result without errors
        - Each observation contains a numeric value
        """
        # Import after mocking to get the callbacks with mocked dependencies
        from open_webui.utils.telemetry.metrics import setup_metrics
        from fastapi import FastAPI
        
        app = FastAPI()
        resource = Resource.create({"service.name": "test-webui"})
        
        # Setup metrics to register the callbacks
        setup_metrics(app, resource)
        
        # Get the meter and find the registered callback
        meter = metrics.get_meter('open_webui.utils.telemetry.metrics')
        
        # We need to access the callback directly
        # Since we can't easily extract it from the meter, we'll import and test it directly
        from open_webui.utils.telemetry import metrics as metrics_module
        
        # Get the callback function
        callback = metrics_module.observe_total_registered_users
        
        # Create mock CallbackOptions
        mock_options = MagicMock(spec=metrics.CallbackOptions)
        
        # Invoke the callback
        result = callback(mock_options)
        
        # BUG CONDITION CHECK: On unfixed code, result will be a coroutine
        # This assertion will FAIL on unfixed code
        assert not inspect.iscoroutine(result), (
            f"Callback returned a coroutine object instead of Sequence[Observation]. "
            f"This is the bug: async callbacks are incompatible with OpenTelemetry SDK. "
            f"Result type: {type(result)}"
        )
        
        # EXPECTED BEHAVIOR CHECK: Result should be a Sequence
        assert isinstance(result, Sequence), (
            f"Callback must return a Sequence[Observation], got {type(result)}"
        )
        
        # EXPECTED BEHAVIOR CHECK: Should be iterable without TypeError
        try:
            observations = list(result)
        except TypeError as e:
            pytest.fail(
                f"Cannot iterate over callback result: {e}. "
                f"This is the bug: OpenTelemetry SDK expects iterable, got coroutine."
            )
        
        # EXPECTED BEHAVIOR CHECK: Each item should be an Observation
        assert len(observations) > 0, "Callback should return at least one observation"
        for obs in observations:
            assert isinstance(obs, metrics.Observation), (
                f"Each item must be an Observation, got {type(obs)}"
            )
            assert isinstance(obs.value, (int, float)), (
                f"Observation value must be numeric, got {type(obs.value)}"
            )
    
    def test_observe_active_users_returns_observations_not_coroutine(
        self, mock_users_model, mock_meter_provider
    ):
        """Test that observe_active_users returns Sequence[Observation], not a coroutine.
        
        **Validates: Requirements 2.1, 2.2, 2.3**
        
        EXPECTED ON UNFIXED CODE: FAIL
        EXPECTED ON FIXED CODE: PASS
        """
        from open_webui.utils.telemetry.metrics import setup_metrics
        from open_webui.utils.telemetry import metrics as metrics_module
        from fastapi import FastAPI
        
        app = FastAPI()
        resource = Resource.create({"service.name": "test-webui"})
        setup_metrics(app, resource)
        
        callback = metrics_module.observe_active_users
        mock_options = MagicMock(spec=metrics.CallbackOptions)
        
        result = callback(mock_options)
        
        # BUG CONDITION CHECK
        assert not inspect.iscoroutine(result), (
            f"observe_active_users returned coroutine instead of Sequence[Observation]"
        )
        
        # EXPECTED BEHAVIOR CHECK
        assert isinstance(result, Sequence)
        
        try:
            observations = list(result)
        except TypeError as e:
            pytest.fail(f"Cannot iterate over callback result: {e}")
        
        assert len(observations) > 0
        for obs in observations:
            assert isinstance(obs, metrics.Observation)
            assert isinstance(obs.value, (int, float))
    
    def test_observe_users_active_today_returns_observations_not_coroutine(
        self, mock_users_model, mock_meter_provider
    ):
        """Test that observe_users_active_today returns Sequence[Observation], not a coroutine.
        
        **Validates: Requirements 2.1, 2.2, 2.3**
        
        EXPECTED ON UNFIXED CODE: FAIL
        EXPECTED ON FIXED CODE: PASS
        """
        from open_webui.utils.telemetry.metrics import setup_metrics
        from open_webui.utils.telemetry import metrics as metrics_module
        from fastapi import FastAPI
        
        app = FastAPI()
        resource = Resource.create({"service.name": "test-webui"})
        setup_metrics(app, resource)
        
        callback = metrics_module.observe_users_active_today
        mock_options = MagicMock(spec=metrics.CallbackOptions)
        
        result = callback(mock_options)
        
        # BUG CONDITION CHECK
        assert not inspect.iscoroutine(result), (
            f"observe_users_active_today returned coroutine instead of Sequence[Observation]"
        )
        
        # EXPECTED BEHAVIOR CHECK
        assert isinstance(result, Sequence)
        
        try:
            observations = list(result)
        except TypeError as e:
            pytest.fail(f"Cannot iterate over callback result: {e}")
        
        assert len(observations) > 0
        for obs in observations:
            assert isinstance(obs, metrics.Observation)
            assert isinstance(obs.value, (int, float))
    
    def test_all_callbacks_are_synchronous_functions(
        self, mock_users_model, mock_meter_provider
    ):
        """Test that all three callbacks are synchronous functions, not coroutine functions.
        
        **Validates: Requirements 2.1, 2.2**
        
        EXPECTED ON UNFIXED CODE: FAIL (callbacks are async def)
        EXPECTED ON FIXED CODE: PASS (callbacks are def)
        """
        from open_webui.utils.telemetry.metrics import setup_metrics
        from open_webui.utils.telemetry import metrics as metrics_module
        from fastapi import FastAPI
        
        app = FastAPI()
        resource = Resource.create({"service.name": "test-webui"})
        setup_metrics(app, resource)
        
        callbacks = [
            ('observe_total_registered_users', metrics_module.observe_total_registered_users),
            ('observe_active_users', metrics_module.observe_active_users),
            ('observe_users_active_today', metrics_module.observe_users_active_today),
        ]
        
        for name, callback in callbacks:
            # BUG CONDITION: On unfixed code, these are coroutine functions (async def)
            assert not inspect.iscoroutinefunction(callback), (
                f"{name} is a coroutine function (async def). "
                f"OpenTelemetry SDK requires synchronous callbacks. "
                f"This is the root cause of the bug."
            )
