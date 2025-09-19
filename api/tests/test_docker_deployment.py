"""
Test Docker deployment and build issues.

This test file is designed to catch issues that only occur in Docker environments,
such as files not being copied properly or import issues in containerized deployments.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest


class TestDockerDeployment:
    """Test Docker-specific deployment issues."""

    def test_all_router_files_exist_in_container_context(self):
        """Test that all router files exist and are accessible.

        This would catch the Docker build cache issue that caused the missing categories.
        """
        # Get the app directory path
        app_dir = Path(__file__).parent.parent / "app"
        routers_dir = app_dir / "routers"

        # List of expected router files
        expected_router_files = [
            "categories.py",
            "feeds.py",
            "health.py",
            "items.py",
            "opml.py",
            "sse.py",
            "__init__.py",
        ]

        missing_files = []
        for router_file in expected_router_files:
            file_path = routers_dir / router_file
            if not file_path.exists():
                missing_files.append(str(file_path))

        assert not missing_files, f"Missing router files: {missing_files}"

    def test_all_router_files_are_importable(self):
        """Test that all router files can be imported without errors.

        This catches syntax errors or missing dependencies that would prevent import.
        """
        import importlib
        import sys

        router_modules = [
            "app.routers.categories",
            "app.routers.feeds",
            "app.routers.health",
            "app.routers.items",
            "app.routers.opml",
            "app.routers.sse",
        ]

        import_errors = []
        for module_name in router_modules:
            try:
                # Force reload to catch any caching issues
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])
                else:
                    importlib.import_module(module_name)
            except Exception as e:
                import_errors.append(f"{module_name}: {e}")

        assert not import_errors, f"Import errors: {import_errors}"

    def test_main_app_can_be_imported_and_instantiated(self):
        """Test that the main FastAPI app can be imported and works.

        This catches issues where the app fails to start due to missing routers.
        """
        from app.main import app

        # Verify the app is properly configured
        assert app is not None
        assert hasattr(app, "routes")
        assert len(app.routes) > 0

        # Verify routers are included
        route_paths = [route.path for route in app.routes]

        # Check for key routes from each router
        required_routes = [
            "/api/v1/categories/",  # Categories router
            "/api/v1/feeds/",  # Feeds router
            "/api/v1/health/liveness",  # Health router
        ]

        missing_routes = [
            route for route in required_routes if route not in route_paths
        ]
        assert not missing_routes, f"Missing routes in main app: {missing_routes}"

    def test_environment_variables_are_accessible(self):
        """Test that required environment variables can be accessed.

        This catches configuration issues in Docker environments.
        """
        from app.core.config import settings

        # Test that settings can be loaded
        assert settings is not None

        # Test that key settings are accessible (even if using defaults)
        assert hasattr(settings, "database_url")
        assert hasattr(settings, "redis_url")
        assert hasattr(settings, "cors_origins")

    def test_database_models_can_be_imported(self):
        """Test that all database models can be imported.

        This catches issues with model definitions or dependencies.
        """
        model_modules = [
            "app.models.category",
            "app.models.feed",
            "app.models.item",
            "app.models.read_state",
            "app.models.fetch_log",
        ]

        import_errors = []
        for module_name in model_modules:
            try:
                __import__(module_name)
            except Exception as e:
                import_errors.append(f"{module_name}: {e}")

        assert not import_errors, f"Model import errors: {import_errors}"

    def test_schema_models_can_be_imported(self):
        """Test that all Pydantic schema models can be imported.

        This catches issues with schema definitions.
        """
        schema_modules = [
            "app.schemas.category",
            "app.schemas.feed",
            "app.schemas.item",
            "app.schemas.read_state",
        ]

        import_errors = []
        for module_name in schema_modules:
            try:
                __import__(module_name)
            except Exception as e:
                import_errors.append(f"{module_name}: {e}")

        assert not import_errors, f"Schema import errors: {import_errors}"

    @pytest.mark.skipif(
        not os.getenv("DOCKER_TEST", False),
        reason="Docker tests only run when DOCKER_TEST=1",
    )
    def test_openapi_schema_generation_in_docker(self):
        """Test OpenAPI schema generation in Docker environment.

        This catches issues that only occur in containerized environments.
        """
        try:
            # This would be run inside a Docker container
            result = subprocess.run(
                ["python", "-c", "from app.main import app; print(app.openapi())"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            assert result.returncode == 0, f"OpenAPI generation failed: {result.stderr}"

            # Try to parse the output as JSON
            schema = json.loads(result.stdout)
            assert "paths" in schema
            assert "/api/v1/categories/" in schema["paths"]

        except subprocess.TimeoutExpired:
            pytest.fail("OpenAPI generation timed out")
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid OpenAPI schema JSON: {e}")


class TestContainerHealthChecks:
    """Test container health and readiness checks."""

    @pytest.mark.asyncio
    async def test_health_endpoints_work_for_container_checks(self, async_client):
        """Test health endpoints that Docker uses for health checks.

        This ensures container health checks will work properly.
        """
        # Test liveness (should always work if app is running)
        liveness_response = await async_client.get("/api/v1/health/liveness")
        assert liveness_response.status_code == 200

        liveness_data = liveness_response.json()
        assert liveness_data["status"] == "ok"

    def test_critical_endpoints_are_documented(self, test_client):
        """Test that critical endpoints are in OpenAPI docs for monitoring.

        This ensures monitoring tools can discover all important endpoints.
        """
        response = test_client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        paths = schema.get("paths", {})

        # Critical endpoints that should be documented
        critical_endpoints = [
            "/api/v1/health/liveness",
            "/api/v1/health/readiness",
            "/api/v1/categories/",
            "/api/v1/feeds/",
        ]

        missing_docs = []
        for endpoint in critical_endpoints:
            if endpoint not in paths:
                missing_docs.append(endpoint)

        assert not missing_docs, f"Critical endpoints missing from docs: {missing_docs}"
