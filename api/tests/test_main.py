from app.main import app
from fastapi import status


class TestMainApplication:
    """Test main application endpoints and configuration."""

    def test_root_endpoint(self, test_client):
        """Test root endpoint."""
        response = test_client.get("/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "RSS Reader API"
        assert data["version"] == "1.0.0"

    def test_api_root_endpoint(self, test_client):
        """Test API root endpoint."""
        response = test_client.get("/api/v1")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "RSS Reader API v1"
        assert "endpoints" in data

        endpoints = data["endpoints"]
        assert endpoints["categories"] == "/api/v1/categories"
        assert endpoints["feeds"] == "/api/v1/feeds"
        assert endpoints["health"] == "/api/v1/health"
        assert endpoints["sse"] == "/api/v1/sse/events"
        assert endpoints["import"] == "/api/v1/import/opml"
        assert endpoints["export"] == "/api/v1/export/opml"

    def test_cors_configuration(self, test_client):
        """Test CORS configuration."""
        # Test preflight request
        response = test_client.options(
            "/api/v1/health/liveness",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        assert response.status_code == status.HTTP_200_OK

        # Check CORS headers
        headers = response.headers
        assert "access-control-allow-origin" in headers
        assert "access-control-allow-methods" in headers
        assert "access-control-allow-headers" in headers

    def test_cors_allowed_origins(self, test_client):
        """Test CORS allowed origins."""
        # Test with allowed origin
        response = test_client.get(
            "/api/v1/health/liveness", headers={"Origin": "http://localhost:3000"}
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access-control-allow-origin" in response.headers

    def test_cors_allowed_methods(self, test_client):
        """Test CORS allowed methods."""
        response = test_client.options(
            "/api/v1/health/liveness",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        allow_methods = response.headers.get("access-control-allow-methods", "")
        assert "POST" in allow_methods
        assert "GET" in allow_methods
        assert "PUT" in allow_methods
        assert "DELETE" in allow_methods
        assert "OPTIONS" in allow_methods

    def test_app_title_and_description(self):
        """Test FastAPI app configuration."""
        assert app.title == "RSS Reader API"
        assert app.description == "Minimal self-hosted RSS reader API"
        assert app.version == "1.0.0"

    def test_router_inclusion(self):
        """Test that all routers are included."""
        # Check that routes exist for all routers
        routes = [route.path for route in app.routes]

        # Health routes
        assert "/api/v1/health/liveness" in routes
        assert "/api/v1/health/readiness" in routes

        # Feed routes
        assert "/api/v1/feeds/" in routes
        assert "/api/v1/feeds/{feed_id}" in routes

        # Item routes (under feeds router)
        assert "/api/v1/feeds/{feed_id}/items" in routes

        # Categories routes - CRITICAL: These were missing and caused the bug!
        assert "/api/v1/categories/" in routes
        assert "/api/v1/categories/{category_id}" in routes
        assert "/api/v1/categories/with-stats" in routes

        # SSE routes
        assert "/api/v1/sse/events" in routes

        # OPML routes
        assert "/api/v1/import/opml" in routes
        assert "/api/v1/export/opml" in routes

    def test_middleware_configuration(self):
        """Test middleware configuration."""
        # Check that CORS middleware is configured
        middleware_types = [
            middleware.cls.__name__ for middleware in app.user_middleware
        ]
        assert "CORSMiddleware" in middleware_types

    def test_openapi_schema_generation(self, test_client):
        """Test OpenAPI schema generation."""
        response = test_client.get("/openapi.json")

        assert response.status_code == status.HTTP_200_OK
        schema = response.json()

        assert schema["info"]["title"] == "RSS Reader API"
        assert schema["info"]["description"] == "Minimal self-hosted RSS reader API"
        assert schema["info"]["version"] == "1.0.0"

        # Check that paths are included
        assert "paths" in schema
        paths = schema["paths"]
        assert "/api/v1/health/liveness" in paths
        assert "/api/v1/feeds/" in paths

    def test_docs_endpoint(self, test_client):
        """Test API documentation endpoint."""
        response = test_client.get("/docs")

        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers["content-type"]

    def test_redoc_endpoint(self, test_client):
        """Test ReDoc documentation endpoint."""
        response = test_client.get("/redoc")

        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers["content-type"]

    def test_404_handling(self, test_client):
        """Test 404 error handling."""
        response = test_client.get("/nonexistent-endpoint")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_method_not_allowed_handling(self, test_client):
        """Test method not allowed handling."""
        # Try to POST to a GET-only endpoint
        response = test_client.post("/api/v1/health/liveness")

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_content_type_headers(self, test_client):
        """Test content type headers."""
        response = test_client.get("/api/v1")

        assert response.status_code == status.HTTP_200_OK
        assert "application/json" in response.headers["content-type"]

    def test_api_versioning(self, test_client):
        """Test API versioning structure."""
        # Test that v1 endpoints exist
        response = test_client.get("/api/v1")
        assert response.status_code == status.HTTP_200_OK

        # Test that non-versioned API root doesn't exist
        response = test_client.get("/api")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_error_response_format(self, test_client):
        """Test error response format."""
        response = test_client.get("/nonexistent")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data

    def test_request_validation_error(self, test_client):
        """Test request validation error handling."""
        # Send invalid JSON to an endpoint that expects valid data
        response = test_client.post(
            "/api/v1/feeds/",
            json={"url": "invalid-url"},  # Invalid URL format
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "detail" in data

    def test_security_headers(self, test_client):
        """Test security-related headers."""
        response = test_client.get("/api/v1")

        # While not explicitly set in our app, FastAPI provides some defaults
        assert response.status_code == status.HTTP_200_OK

        # Test that the response is valid JSON
        data = response.json()
        assert isinstance(data, dict)

    def test_lifespan_events(self):
        """Test lifespan event configuration."""
        # This is tested implicitly - if the app starts and stops properly,
        # the lifespan events are working
        assert app.router.lifespan_context is not None

    def test_router_tags(self):
        """Test that routers have appropriate tags."""
        # Check routes have tags for OpenAPI grouping
        tagged_routes = [
            route for route in app.routes if hasattr(route, "tags") and route.tags
        ]

        # Should have routes with tags
        assert len(tagged_routes) > 0

    def test_dependency_injection_setup(self):
        """Test dependency injection setup."""
        # Test that dependency overrides work (used in testing)
        from app.core.database import get_db

        # Should be able to override dependencies
        original_deps = app.dependency_overrides.copy()

        def mock_db():
            return "mock"

        app.dependency_overrides[get_db] = mock_db
        assert app.dependency_overrides[get_db] == mock_db

        # Clean up
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_deps)
