"""Standalone preservation property tests for OpenTelemetry metrics.

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

import sys
import time
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource


def create_test_app_with_metrics():
    """Create a FastAPI app with metrics middleware and test routes."""
    # Mock the Users model before importing metrics module
    import sys
    import importlib
    
    # Mock the Users model in sys.modules before importing
    from unittest.mock import MagicMock
    mock_users = MagicMock()
    mock_users.get_num_users = AsyncMock(return_value=100)
    mock_users.get_active_user_count = AsyncMock(return_value=50)
    mock_users.get_num_users_active_today = AsyncMock(return_value=25)
    
    # Inject mock into sys.modules
    if 'open_webui.models.users' not in sys.modules:
        mock_models = MagicMock()
        mock_models.users = MagicMock()
        mock_models.users.Users = mock_users
        sys.modules['open_webui.models'] = mock_models
        sys.modules['open_webui.models.users'] = mock_models.users
    
    # Now import the metrics module
    from open_webui.utils.telemetry import metrics as metrics_module
    
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
    metrics_module.setup_metrics(app, resource)
    
    return app, reader


def test_http_request_counter_increments_for_get_requests():
    """Test that http.server.requests counter increments for GET requests.
    
    **Validates: Requirement 3.1**
    
    EXPECTED: Counter increments by 1 for each GET request
    """
    print("\n" + "="*70)
    print("TEST: HTTP Request Counter - GET Requests")
    print("="*70)
    
    app, reader = create_test_app_with_metrics()
    client = TestClient(app)
    
    # Make a GET request
    response = client.get("/test")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
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
    print("✓ http.server.requests metric found")
    
    # Verify the counter has data points
    assert len(request_counter.data.data_points) > 0, "No data points in counter"
    print(f"✓ Counter has {len(request_counter.data.data_points)} data point(s)")
    
    # Find the data point for our GET /test request
    test_route_point = None
    for point in request_counter.data.data_points:
        attrs = {attr.key: attr.value.value for attr in point.attributes}
        if attrs.get("http.method") == "GET" and attrs.get("http.route") == "/test":
            test_route_point = point
            break
    
    assert test_route_point is not None, "Data point for GET /test not found"
    assert test_route_point.value >= 1, "Counter should have incremented"
    print(f"✓ Counter value for GET /test: {test_route_point.value}")
    print("✓ PASS: HTTP request counter increments for GET requests")


def test_http_duration_histogram_records_request_duration():
    """Test that http.server.duration histogram records request durations.
    
    **Validates: Requirement 3.1**
    
    EXPECTED: Histogram records duration in milliseconds for each request
    """
    print("\n" + "="*70)
    print("TEST: HTTP Duration Histogram - Request Duration")
    print("="*70)
    
    app, reader = create_test_app_with_metrics()
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
    print("✓ http.server.duration metric found")
    
    # Verify the histogram has data points
    assert len(duration_histogram.data.data_points) > 0, "No data points in histogram"
    print(f"✓ Histogram has {len(duration_histogram.data.data_points)} data point(s)")
    
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
    print(f"✓ Histogram count: {test_route_point.count}, sum: {test_route_point.sum}ms")
    print("✓ PASS: HTTP duration histogram records request duration")


def test_middleware_captures_status_codes():
    """Test that middleware captures status codes for requests.
    
    **Validates: Requirement 3.1**
    
    EXPECTED: Metrics include http.status_code attribute
    """
    print("\n" + "="*70)
    print("TEST: Middleware - Status Code Capture")
    print("="*70)
    
    app, reader = create_test_app_with_metrics()
    client = TestClient(app)
    
    # Make a successful request
    response = client.get("/test")
    assert response.status_code == 200
    
    # Make a request that raises an error
    try:
        response = client.get("/error")
    except Exception:
        pass  # Expected to raise
    
    # Collect metrics
    metrics_data = reader.get_metrics_data()
    
    # Find metrics with status codes
    status_codes_found = set()
    for resource_metrics in metrics_data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                if metric.name in ["http.server.requests", "http.server.duration"]:
                    for point in metric.data.data_points:
                        attrs = {attr.key: attr.value.value for attr in point.attributes}
                        status_code = attrs.get("http.status_code")
                        if status_code:
                            status_codes_found.add(status_code)
    
    assert 200 in status_codes_found, "Middleware should capture status code 200"
    print(f"✓ Status codes captured: {sorted(status_codes_found)}")
    print("✓ PASS: Middleware captures status codes")


def test_middleware_captures_route_templates():
    """Test that middleware captures route templates, not actual paths.
    
    **Validates: Requirement 3.1**
    
    EXPECTED: Route is captured as template "/api/items/{item_id}", not "/api/items/123"
    """
    print("\n" + "="*70)
    print("TEST: Middleware - Route Template Capture")
    print("="*70)
    
    app, reader = create_test_app_with_metrics()
    client = TestClient(app)
    
    # Make a request with a path parameter
    response = client.get("/api/items/123")
    assert response.status_code == 200
    
    # Collect metrics
    metrics_data = reader.get_metrics_data()
    
    # Find metrics for the items route
    routes_found = set()
    for resource_metrics in metrics_data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                if metric.name in ["http.server.requests", "http.server.duration"]:
                    for point in metric.data.data_points:
                        attrs = {attr.key: attr.value.value for attr in point.attributes}
                        route = attrs.get("http.route")
                        if route and "items" in route:
                            routes_found.add(route)
    
    # Should be the template, not the actual path
    assert "/api/items/{item_id}" in routes_found, (
        f"Middleware should capture route template, found: {routes_found}"
    )
    print(f"✓ Routes captured: {routes_found}")
    print("✓ PASS: Middleware captures route templates")


def test_middleware_captures_http_methods():
    """Test that middleware captures HTTP method for all requests.
    
    **Validates: Requirement 3.1**
    
    EXPECTED: Metrics include http.method attribute (GET, POST, etc.)
    """
    print("\n" + "="*70)
    print("TEST: Middleware - HTTP Method Capture")
    print("="*70)
    
    app, reader = create_test_app_with_metrics()
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
    print(f"✓ HTTP methods captured: {sorted(methods_seen)}")
    print("✓ PASS: Middleware captures HTTP methods")


def test_meter_provider_has_correct_resource_attributes():
    """Test that MeterProvider has correct resource attributes.
    
    **Validates: Requirement 3.4**
    
    EXPECTED: Resource includes service.name attribute
    """
    print("\n" + "="*70)
    print("TEST: MeterProvider - Resource Attributes")
    print("="*70)
    
    app, reader = create_test_app_with_metrics()
    
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
        print(f"✓ Resource attributes: {dict(attrs)}")
        print("✓ PASS: MeterProvider has correct resource attributes")
        return
    
    raise AssertionError("No resource metrics found")


def test_all_expected_metrics_are_registered():
    """Test that all expected metrics are registered and collecting data.
    
    **Validates: Requirements 3.1, 3.3**
    
    EXPECTED: Both http.server.requests and http.server.duration metrics exist
    """
    print("\n" + "="*70)
    print("TEST: Metrics Registration - All Expected Metrics")
    print("="*70)
    
    app, reader = create_test_app_with_metrics()
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
    print(f"✓ Metrics registered: {sorted(metric_names)}")
    print("✓ PASS: All expected metrics are registered")


def main():
    """Run all preservation property tests."""
    print("="*70)
    print("OpenTelemetry Metrics Preservation Property Tests")
    print("="*70)
    print("\nTask 2: Write preservation property tests (BEFORE implementing fix)")
    print("\nThese tests verify that non-observable metrics continue to work")
    print("correctly on UNFIXED code and after the fix is applied.")
    print("\nExpected outcome: All tests PASS on unfixed code (baseline behavior)")
    print("Expected outcome: All tests PASS on fixed code (no regressions)")
    
    tests = [
        ("HTTP Request Counter - GET", test_http_request_counter_increments_for_get_requests),
        ("HTTP Duration Histogram", test_http_duration_histogram_records_request_duration),
        ("Middleware Status Codes", test_middleware_captures_status_codes),
        ("Middleware Route Templates", test_middleware_captures_route_templates),
        ("Middleware HTTP Methods", test_middleware_captures_http_methods),
        ("MeterProvider Resources", test_meter_provider_has_correct_resource_attributes),
        ("Metrics Registration", test_all_expected_metrics_are_registered),
    ]
    
    passed = 0
    failed = 0
    errors = []
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            failed += 1
            errors.append((test_name, str(e)))
            print(f"❌ FAIL: {test_name}")
            print(f"   Error: {e}")
        except Exception as e:
            failed += 1
            errors.append((test_name, f"Exception: {e}"))
            print(f"❌ ERROR: {test_name}")
            print(f"   Exception: {e}")
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Total: {len(tests)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed > 0:
        print("\n" + "="*70)
        print("FAILED TESTS")
        print("="*70)
        for test_name, error in errors:
            print(f"\n{test_name}:")
            print(f"  {error}")
        return 1
    else:
        print("\n" + "="*70)
        print("CONCLUSION: All preservation tests PASS!")
        print("="*70)
        print("\nBaseline behavior confirmed:")
        print("- HTTP request counter increments correctly")
        print("- HTTP duration histogram records durations accurately")
        print("- Middleware captures status codes, routes, and methods")
        print("- MeterProvider configuration is correct")
        print("- All expected metrics are registered")
        print("\nThese behaviors must be preserved after the fix is applied.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
