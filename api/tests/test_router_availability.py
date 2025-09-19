"""
Test router availability and inclusion.

This test file is specifically designed to catch issues where routers
are implemented but not properly included in the main application.
This prevents bugs like the missing categories API that occurred.
"""

import pytest
from app.main import app
from fastapi import status


class TestRouterAvailability:
    """Test that all expected routers are available and working."""

    def test_all_expected_routers_are_imported(self):
        """Test that all expected router modules can be imported.

        This catches import errors that would prevent routers from being included.
        """
        # Test direct imports - this will fail if there are syntax errors
        from app.routers import categories, feeds, health, items, opml, sse

        # Verify each router has the expected router object
        assert hasattr(categories, "router")
        assert hasattr(feeds, "router")
        assert hasattr(health, "router")
        assert hasattr(items, "router")
        assert hasattr(opml, "router")
        assert hasattr(sse, "router")

    def test_all_routers_included_in_main_app(self):
        """Test that all routers are properly included in the main FastAPI app.

        This is the test that would have caught the missing categories bug.
        """
        routes = [route.path for route in app.routes]

        # Define all expected core routes for each router
        expected_routes = {
            "categories": [
                "/api/v1/categories/",
                "/api/v1/categories/{category_id}",
                "/api/v1/categories/with-stats",
            ],
            "feeds": [
                "/api/v1/feeds/",
                "/api/v1/feeds/{feed_id}",
                "/api/v1/feeds/{feed_id}/items",
            ],
            "health": [
                "/api/v1/health/liveness",
                "/api/v1/health/readiness",
            ],
            "items": [
                "/api/v1/feeds/items/{item_id}",
                "/api/v1/feeds/items/{item_id}/read",
            ],
            "opml": [
                "/api/v1/import/opml",
                "/api/v1/export/opml",
            ],
            "sse": [
                "/api/v1/sse/events",
            ],
        }

        # Check each router's routes are present
        missing_routes = []
        for router_name, router_routes in expected_routes.items():
            for route in router_routes:
                if route not in routes:
                    missing_routes.append(f"{router_name}: {route}")

        assert not missing_routes, f"Missing routes: {missing_routes}"

    @pytest.mark.asyncio
    async def test_all_core_endpoints_respond(self, async_client):
        """Test that all core endpoints respond (not 404).

        This ensures routers are not only included but actually working.
        """
        # Test one core endpoint from each router
        # Note: SSE endpoint excluded as it requires Redis connection
        core_endpoints = [
            ("/api/v1/categories/", "Categories router"),
            ("/api/v1/feeds/", "Feeds router"),
            ("/api/v1/health/liveness", "Health router"),
            ("/api/v1/export/opml", "OPML router"),
        ]

        failed_endpoints = []
        for endpoint, description in core_endpoints:
            response = await async_client.get(endpoint)
            if response.status_code == status.HTTP_404_NOT_FOUND:
                failed_endpoints.append(f"{description}: {endpoint}")

        assert not failed_endpoints, f"Endpoints returning 404: {failed_endpoints}"

    def test_api_documentation_includes_all_routers(self, test_client):
        """Test that OpenAPI documentation includes all router endpoints.

        This catches cases where routers are included but not generating docs.
        """
        response = test_client.get("/openapi.json")
        assert response.status_code == status.HTTP_200_OK

        schema = response.json()
        paths = schema.get("paths", {})

        # Check that each router contributes paths to the schema
        router_path_prefixes = [
            "/api/v1/categories",
            "/api/v1/feeds",
            "/api/v1/health",
            "/api/v1/sse",
            "/api/v1/import",
            "/api/v1/export",
        ]

        missing_prefixes = []
        for prefix in router_path_prefixes:
            # Check if any path starts with this prefix
            has_prefix = any(path.startswith(prefix) for path in paths.keys())
            if not has_prefix:
                missing_prefixes.append(prefix)

        assert not missing_prefixes, (
            f"Missing router paths in OpenAPI: {missing_prefixes}"
        )

    def test_api_root_endpoint_lists_all_routers(self, test_client):
        """Test that the API root endpoint lists all available routers.

        This ensures the API discovery endpoint is complete.
        """
        response = test_client.get("/api/v1")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        endpoints = data.get("endpoints", {})

        # All routers should be listed in the API root
        expected_endpoints = [
            "categories",
            "feeds",
            "health",
            "sse",
            "import",
            "export",
        ]

        missing_endpoints = []
        for endpoint_key in expected_endpoints:
            if endpoint_key not in endpoints:
                missing_endpoints.append(endpoint_key)

        assert not missing_endpoints, (
            f"Missing endpoints in API root: {missing_endpoints}"
        )

    @pytest.mark.asyncio
    async def test_router_error_handling_works(self, async_client):
        """Test that router error handling is working properly.

        This ensures routers are not only included but properly configured.
        """
        # Test that invalid requests return proper error responses (not 500)
        test_cases = [
            ("/api/v1/categories/invalid-uuid", "Invalid category ID"),
            ("/api/v1/feeds/invalid-uuid", "Invalid feed ID"),
        ]

        for endpoint, description in test_cases:
            response = await async_client.get(endpoint)
            # Should return 422 (validation error) or 404, not 500 (server error)
            assert response.status_code in [
                status.HTTP_404_NOT_FOUND,
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            ], f"{description} at {endpoint} returned {response.status_code}"


class TestRouterIntegration:
    """Test integration between routers to ensure they work together."""

    @pytest.mark.asyncio
    async def test_cross_router_functionality(self, async_client, db_session):
        """Test that routers can work together (e.g., feeds and categories).

        This ensures routers are not just individually working but integrated.
        """
        # This is a basic integration test - more specific ones exist in other files

        # Test that we can access both feeds and categories
        feeds_response = await async_client.get("/api/v1/feeds/")
        categories_response = await async_client.get("/api/v1/categories/")

        assert feeds_response.status_code == status.HTTP_200_OK
        assert categories_response.status_code == status.HTTP_200_OK

        # Both should return arrays (empty is fine)
        feeds_data = feeds_response.json()
        categories_data = categories_response.json()

        assert isinstance(feeds_data, list)
        assert isinstance(categories_data, list)
