"""Preservation property tests for OpenTelemetry metrics.

Task 2: Write preservation property tests (BEFORE implementing fix)

**Property 2: Preservation** - Non-Observable Metrics Behavior Unchanged

**IMPORTANT**: Follow observation-first methodology
- Observe behavior on UNFIXED code for non-observable metrics
- Record actual metric values collected for sample HTTP requests
- Write property-based tests capturing observed behavior patterns

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

These tests verify that:
- http.server.requests counter increments correctly for various HTTP methods and routes
- http.server.duration histogram records request durations accurately
- FastAPI middleware continues to capture status codes, routes, and timing
- All non-observable metrics continue working after the fix

EXPECTED ON UNFIXED CODE: Tests PASS (confirms baseline behavior to preserve)
EXPECTED ON FIXED CODE: Tests PASS (confirms no regressions)
"""

import pytest
import time
from typing import Dict, List
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource


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
def app_with_metrics(mock_users_model):
    """Create a FastAPI app with metrics middleware and test routes."""
    # Create a fresh FastAPI app
    app = FastAPI()
    
    # Add test routes
    @app.get("/test")
    async def test_route():
        return {"message": "test"}
    
    @app.post("/api/users")
    async def create_user():
        return {"id": 1, "name": "test"}
    
    @app.get("/api/items/{item_id}")
    async def get_item(item_id: int):
        return {"id": item_id}
    
    @app.get("/slow")
    async def slow_route():
        # Simulate a slow endpoint
        time.sleep(0.1)
        return {"message": "slow"}
    
    @app.get("/error")
    async def error_route():
        raise ValueError("Test error")
    
    # Create an in-memory metric reader for testing
    reader = InMemoryMetricReader()
    resource = Resource.create({"service.name": "test-webui"})
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)
    
    # Setup metrics (this adds the middleware)
    from open_webui.utils.telemetry.metrics import setup_metrics
    setup_metrics(app, resource)
    
    return app, reader


class TestHTTPMetricsPreservation:
    """Test that HTTP metrics (counter and histogram) continue to work correctly.
    
    **Property 2: Preservation** - Non-Observable Metrics Behavior Unchanged
    
    **Validates: Requirements 3.1, 3.3**
    
    These tests verify that the http.server.requests counter and http.server.duration
    histogram continue to collect metrics correctly for various HTTP methods, routes,
    and status codes.
    """
    
    def test_http_request_counter_increments_for_get_requests(self, app_with_metrics):
        """Test that http.server.requests counter increments for GET requests.
        
        **Validates: Requirement 3.1**
        
        EXPECTED: Counter increments by 1 for each GET request
        """
        app, reader = app_with_metrics
        client = TestClient(app)
        
        # Make a GET request
        response = client.get("/test")
        assert response.status_code == 200
        
        # Collect metrics
        metrics_data = reader.get_metrics_data()
        
        # Find the request counter metric
        request_counter = None
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name == "http.server.requests":
                        request_counter = metric
                        break
        
        assert request_counter is not None, "http.server.requests metric not found"
        
        # Verify the counter has data points
        assert len(request_counter.data.data_points) > 0, "No data points in counter"
        
        # Find the data point for our GET /test request
        test_route_point = None
        for point in request_counter.data.data_points:
            attrs = {attr.key: attr.value.value for attr in point.attributes}
            if attrs.get("http.method") == "GET" and attrs.get("http.route") == "/test":
                test_route_point = point
                break
        
        assert test_route_point is not None, "Data point for GET /test not found"
        assert test_route_point.value >= 1, "Counter should have incremented"
    
    def test_http_request_counter_increments_for_post_requests(self, app_with_metrics):
        """Test that http.server.requests counter increments for POST requests.
        
        **Validates: Requirement 3.1**
        
        EXPECTED: Counter increments by 1 for each POST request
        """
        app, reader = app_with_metrics
        client = TestClient(app)
        
        # Make a POST request
        response = client.post("/api/users", json={"name": "test"})
        assert response.status_code == 200
        
        # Collect metrics
        metrics_data = reader.get_metrics_data()
        
        # Find the request counter metric
        request_counter = None
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name == "http.server.requests":
                        request_counter = metric
                        break
        
        assert request_counter is not None, "http.server.requests metric not found"
        
        # Find the data point for our POST request
        post_route_point = None
        for point in request_counter.data.data_points:
            attrs = {attr.key: attr.value.value for attr in point.attributes}
            if attrs.get("http.method") == "POST" and attrs.get("http.route") == "/api/users":
                post_route_point = point
                break
        
        assert post_route_point is not None, "Data point for POST /api/users not found"
        assert post_route_point.value >= 1, "Counter should have incremented"
    
    def test_http_request_counter_tracks_multiple_routes(self, app_with_metrics):
        """Test that http.server.requests counter tracks different routes separately.
        
        **Validates: Requirement 3.1**
        
        EXPECTED: Each route has its own counter value
        """
        app, reader = app_with_metrics
        client = TestClient(app)
        
        # Make requests to different routes
        client.get("/test")
        client.get("/api/items/123")
        client.post("/api/users")
        
        # Collect metrics
        metrics_data = reader.get_metrics_data()
        
        # Find the request counter metric
        request_counter = None
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name == "http.server.requests":
                        request_counter = metric
                        break
        
        assert request_counter is not None, "http.server.requests metric not found"
        
        # Verify we have data points for different routes
        routes_seen = set()
        for point in request_counter.data.data_points:
            attrs = {attr.key: attr.value.value for attr in point.attributes}
            route = attrs.get("http.route")
            if route:
                routes_seen.add(route)
        
        # We should see at least 3 different routes
        assert len(routes_seen) >= 3, f"Expected at least 3 routes, got {routes_seen}"
    
    def test_http_duration_histogram_records_request_duration(self, app_with_metrics):
        """Test that http.server.duration histogram records request durations.
        
        **Validates: Requirement 3.1**
        
        EXPECTED: Histogram records duration in milliseconds for each request
        """
        app, reader = app_with_metrics
        client = TestClient(app)
        
        # Make a request
        response = client.get("/test")
        assert response.status_code == 200
        
        # Collect metrics
        metrics_data = reader.get_metrics_data()
        
        # Find the duration histogram metric
        duration_histogram = None
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name == "http.server.duration":
                        duration_histogram = metric
                        break
        
        assert duration_histogram is not None, "http.server.duration metric not found"
        
        # Verify the histogram has data points
        assert len(duration_histogram.data.data_points) > 0, "No data points in histogram"
        
        # Find the data point for our GET /test request
        test_route_point = None
        for point in duration_histogram.data.data_points:
            attrs = {attr.key: attr.value.value for attr in point.attributes}
            if attrs.get("http.method") == "GET" and attrs.get("http.route") == "/test":
                test_route_point = point
                break
        
        assert test_route_point is not None, "Data point for GET /test not found"
        assert test_route_point.count >= 1, "Histogram should have recorded at least one request"
        assert test_route_point.sum > 0, "Histogram sum should be positive (duration in ms)"
    
    def test_http_duration_histogram_records_slow_requests(self, app_with_metrics):
        """Test that http.server.duration histogram accurately records slow requests.
        
        **Validates: Requirement 3.1**
        
        EXPECTED: Histogram records duration >= 100ms for slow endpoint
        """
        app, reader = app_with_metrics
        client = TestClient(app)
        
        # Make a request to the slow endpoint
        response = client.get("/slow")
        assert response.status_code == 200
        
        # Collect metrics
        metrics_data = reader.get_metrics_data()
        
        # Find the duration histogram metric
        duration_histogram = None
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name == "http.server.duration":
                        duration_histogram = metric
                        break
        
        assert duration_histogram is not None, "http.server.duration metric not found"
        
        # Find the data point for our slow request
        slow_route_point = None
        for point in duration_histogram.data.data_points:
            attrs = {attr.key: attr.value.value for attr in point.attributes}
            if attrs.get("http.route") == "/slow":
                slow_route_point = point
                break
        
        assert slow_route_point is not None, "Data point for GET /slow not found"
        assert slow_route_point.count >= 1, "Histogram should have recorded the slow request"
        
        # The average duration should be at least 100ms (we sleep for 0.1s)
        avg_duration = slow_route_point.sum / slow_route_point.count
        assert avg_duration >= 100, f"Expected duration >= 100ms, got {avg_duration}ms"


class TestMiddlewarePreservation:
    """Test that FastAPI middleware continues to capture status codes, routes, and timing.
    
    **Property 2: Preservation** - Middleware Behavior Unchanged
    
    **Validates: Requirements 3.1, 3.3**
    
    These tests verify that the FastAPI middleware continues to work correctly,
    capturing HTTP method, route, status code, and timing information.
    """
    
    def test_middleware_captures_status_code_200(self, app_with_metrics):
        """Test that middleware captures status code 200 for successful requests.
        
        **Validates: Requirement 3.1**
        
        EXPECTED: Metrics include http.status_code=200 attribute
        """
        app, reader = app_with_metrics
        client = TestClient(app)
        
        # Make a successful request
        response = client.get("/test")
        assert response.status_code == 200
        
        # Collect metrics
        metrics_data = reader.get_metrics_data()
        
        # Find metrics with status code 200
        found_200 = False
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name in ["http.server.requests", "http.server.duration"]:
                        for point in metric.data.data_points:
                            attrs = {attr.key: attr.value.value for attr in point.attributes}
                            if attrs.get("http.status_code") == 200:
                                found_200 = True
                                break
        
        assert found_200, "Middleware should capture status code 200"
    
    def test_middleware_captures_status_code_500_on_error(self, app_with_metrics):
        """Test that middleware captures status code 500 for errors.
        
        **Validates: Requirement 3.1**
        
        EXPECTED: Metrics include http.status_code=500 attribute for errors
        """
        app, reader = app_with_metrics
        client = TestClient(app)
        
        # Make a request that raises an error
        try:
            response = client.get("/error")
        except Exception:
            pass  # Expected to raise
        
        # Collect metrics
        metrics_data = reader.get_metrics_data()
        
        # Find metrics with status code 500
        found_500 = False
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name in ["http.server.requests", "http.server.duration"]:
                        for point in metric.data.data_points:
                            attrs = {attr.key: attr.value.value for attr in point.attributes}
                            if attrs.get("http.status_code") == 500:
                                found_500 = True
                                break
        
        assert found_500, "Middleware should capture status code 500 for errors"
    
    def test_middleware_captures_route_templates(self, app_with_metrics):
        """Test that middleware captures route templates, not actual paths.
        
        **Validates: Requirement 3.1**
        
        EXPECTED: Route is captured as template "/api/items/{item_id}", not "/api/items/123"
        """
        app, reader = app_with_metrics
        client = TestClient(app)
        
        # Make a request with a path parameter
        response = client.get("/api/items/123")
        assert response.status_code == 200
        
        # Collect metrics
        metrics_data = reader.get_metrics_data()
        
        # Find metrics for the items route
        found_template = False
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name in ["http.server.requests", "http.server.duration"]:
                        for point in metric.data.data_points:
                            attrs = {attr.key: attr.value.value for attr in point.attributes}
                            route = attrs.get("http.route")
                            # Should be the template, not the actual path
                            if route == "/api/items/{item_id}":
                                found_template = True
                                break
        
        assert found_template, "Middleware should capture route template, not actual path"
    
    def test_middleware_captures_http_method(self, app_with_metrics):
        """Test that middleware captures HTTP method for all requests.
        
        **Validates: Requirement 3.1**
        
        EXPECTED: Metrics include http.method attribute (GET, POST, etc.)
        """
        app, reader = app_with_metrics
        client = TestClient(app)
        
        # Make requests with different methods
        client.get("/test")
        client.post("/api/users")
        
        # Collect metrics
        metrics_data = reader.get_metrics_data()
        
        # Find metrics with different HTTP methods
        methods_seen = set()
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name in ["http.server.requests", "http.server.duration"]:
                        for point in metric.data.data_points:
                            attrs = {attr.key: attr.value.value for attr in point.attributes}
                            method = attrs.get("http.method")
                            if method:
                                methods_seen.add(method)
        
        assert "GET" in methods_seen, "Should capture GET method"
        assert "POST" in methods_seen, "Should capture POST method"
    
    def test_middleware_timing_is_accurate(self, app_with_metrics):
        """Test that middleware timing measurements are accurate.
        
        **Validates: Requirement 3.1**
        
        EXPECTED: Duration measurements are reasonable (> 0ms, < 1000ms for fast endpoints)
        """
        app, reader = app_with_metrics
        client = TestClient(app)
        
        # Make a request to a fast endpoint
        response = client.get("/test")
        assert response.status_code == 200
        
        # Collect metrics
        metrics_data = reader.get_metrics_data()
        
        # Find the duration histogram
        duration_histogram = None
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name == "http.server.duration":
                        duration_histogram = metric
                        break
        
        assert duration_histogram is not None, "http.server.duration metric not found"
        
        # Check that durations are reasonable
        for point in duration_histogram.data.data_points:
            attrs = {attr.key: attr.value.value for attr in point.attributes}
            if attrs.get("http.route") == "/test":
                avg_duration = point.sum / point.count
                # Fast endpoint should be < 1000ms
                assert 0 < avg_duration < 1000, (
                    f"Duration should be reasonable (0-1000ms), got {avg_duration}ms"
                )


class TestMetricsConfigurationPreservation:
    """Test that MeterProvider configuration and OTLP exporter setup remain unchanged.
    
    **Property 2: Preservation** - Configuration Unchanged
    
    **Validates: Requirements 3.4, 3.5**
    
    These tests verify that the OpenTelemetry configuration (MeterProvider, views,
    resource attributes) continues to work correctly.
    """
    
    def test_meter_provider_has_correct_resource_attributes(self, app_with_metrics):
        """Test that MeterProvider has correct resource attributes.
        
        **Validates: Requirement 3.4**
        
        EXPECTED: Resource includes service.name attribute
        """
        app, reader = app_with_metrics
        
        # Collect metrics
        metrics_data = reader.get_metrics_data()
        
        # Check resource attributes
        for resource_metrics in metrics_data.resource_metrics:
            resource = resource_metrics.resource
            attrs = {attr.key: attr.value for attr in resource.attributes}
            
            assert "service.name" in attrs, "Resource should have service.name attribute"
            assert attrs["service.name"] == "test-webui", (
                f"Expected service.name='test-webui', got '{attrs['service.name']}'"
            )
    
    def test_all_expected_metrics_are_registered(self, app_with_metrics):
        """Test that all expected metrics are registered and collecting data.
        
        **Validates: Requirements 3.1, 3.3**
        
        EXPECTED: Both http.server.requests and http.server.duration metrics exist
        """
        app, reader = app_with_metrics
        client = TestClient(app)
        
        # Make a request to generate metrics
        client.get("/test")
        
        # Collect metrics
        metrics_data = reader.get_metrics_data()
        
        # Find all metric names
        metric_names = set()
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    metric_names.add(metric.name)
        
        # Verify expected metrics are present
        assert "http.server.requests" in metric_names, (
            "http.server.requests metric should be registered"
        )
        assert "http.server.duration" in metric_names, (
            "http.server.duration metric should be registered"
        )
