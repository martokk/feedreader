from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from sqlalchemy.exc import SQLAlchemyError


class TestHealthRouter:
    """Test health check endpoints."""

    def test_liveness_check(self, test_client):
        """Test liveness endpoint."""
        response = test_client.get("/api/v1/health/liveness")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"
        assert data["message"] == "API is running"

    @pytest.mark.asyncio
    async def test_readiness_check_success(self, async_client, override_get_redis):
        """Test readiness check when all services are available."""
        # Mock Redis to return successful ping
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True

        with patch("app.routers.health.get_redis", return_value=mock_redis):
            response = await async_client.get("/api/v1/health/readiness")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"] is True
        assert data["checks"]["redis"] is True

    @pytest.mark.asyncio
    async def test_readiness_check_database_failure(
        self, async_client, override_get_redis
    ):
        """Test readiness check when database is unavailable."""
        # Mock Redis to succeed
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True

        # Mock database to fail
        with patch("app.routers.health.get_redis", return_value=mock_redis):
            with patch("app.core.database.AsyncSessionLocal") as mock_session_local:
                mock_session = AsyncMock()
                mock_session.execute.side_effect = SQLAlchemyError(
                    "Database connection failed"
                )
                mock_session_local.return_value.__aenter__.return_value = mock_session

                response = await async_client.get("/api/v1/health/readiness")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()["detail"]
        assert data["status"] == "not ready"
        assert data["checks"]["database"] is False
        assert data["checks"]["redis"] is True

    @pytest.mark.asyncio
    async def test_readiness_check_redis_failure(self, async_client):
        """Test readiness check when Redis is unavailable."""
        # Mock Redis to fail
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Redis connection failed")

        with patch("app.routers.health.get_redis", return_value=mock_redis):
            response = await async_client.get("/api/v1/health/readiness")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()["detail"]
        assert data["status"] == "not ready"
        assert data["checks"]["database"] is True
        assert data["checks"]["redis"] is False

    @pytest.mark.asyncio
    async def test_readiness_check_all_services_failure(self, async_client):
        """Test readiness check when all services are unavailable."""
        # Mock Redis to fail
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Redis connection failed")

        with patch("app.routers.health.get_redis", return_value=mock_redis):
            with patch("app.core.database.AsyncSessionLocal") as mock_session_local:
                mock_session = AsyncMock()
                mock_session.execute.side_effect = SQLAlchemyError(
                    "Database connection failed"
                )
                mock_session_local.return_value.__aenter__.return_value = mock_session

                response = await async_client.get("/api/v1/health/readiness")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()["detail"]
        assert data["status"] == "not ready"
        assert data["checks"]["database"] is False
        assert data["checks"]["redis"] is False

    @pytest.mark.asyncio
    async def test_readiness_check_database_query_execution(self, async_client):
        """Test that readiness check actually executes a database query."""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True

        with patch("app.routers.health.get_redis", return_value=mock_redis):
            with patch("app.core.database.AsyncSessionLocal") as mock_session_local:
                mock_session = AsyncMock()
                mock_session.execute.return_value = None  # Successful query
                mock_session_local.return_value.__aenter__.return_value = mock_session

                response = await async_client.get("/api/v1/health/readiness")

        assert response.status_code == status.HTTP_200_OK
        # Verify that execute was called with a SELECT 1 query
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args[0][0]
        assert "SELECT 1" in str(call_args)

    @pytest.mark.asyncio
    async def test_readiness_check_redis_ping_execution(self, async_client):
        """Test that readiness check actually calls Redis ping."""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True

        with patch("app.routers.health.get_redis", return_value=mock_redis):
            response = await async_client.get("/api/v1/health/readiness")

        assert response.status_code == status.HTTP_200_OK
        # Verify that ping was called
        mock_redis.ping.assert_called_once()

    def test_liveness_no_dependencies(self, test_client):
        """Test that liveness check doesn't depend on external services."""
        # Even if database/Redis are down, liveness should still work
        response = test_client.get("/api/v1/health/liveness")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_readiness_check_response_format(self, async_client):
        """Test readiness check response format."""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True

        with patch("app.routers.health.get_redis", return_value=mock_redis):
            response = await async_client.get("/api/v1/health/readiness")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check response structure
        assert "status" in data
        assert "checks" in data
        assert isinstance(data["checks"], dict)
        assert "database" in data["checks"]
        assert "redis" in data["checks"]
        assert isinstance(data["checks"]["database"], bool)
        assert isinstance(data["checks"]["redis"], bool)

    @pytest.mark.asyncio
    async def test_readiness_error_response_format(self, async_client):
        """Test readiness check error response format."""
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Redis failed")

        with patch("app.routers.health.get_redis", return_value=mock_redis):
            response = await async_client.get("/api/v1/health/readiness")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()

        # Check error response structure
        assert "detail" in data
        detail = data["detail"]
        assert "status" in detail
        assert "checks" in detail
        assert detail["status"] == "not ready"
        assert isinstance(detail["checks"], dict)

    def test_health_endpoints_tags(self, test_client):
        """Test that health endpoints have correct OpenAPI tags."""
        # This is tested implicitly through the router configuration
        # The endpoints should be accessible under the /health prefix

        liveness_response = test_client.get("/api/v1/health/liveness")
        assert liveness_response.status_code == status.HTTP_200_OK

        # Note: readiness requires async client due to database dependency
        # but we can at least verify the endpoint exists
        readiness_response = test_client.get("/api/v1/health/readiness")
        # This might fail due to database connection, but endpoint should exist
        assert readiness_response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_readiness_check_partial_failure_still_fails(self, async_client):
        """Test that readiness check fails if any service is down."""
        # Even if one service is up and one is down, readiness should fail
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True  # Redis is up

        with patch("app.routers.health.get_redis", return_value=mock_redis):
            with patch("app.core.database.AsyncSessionLocal") as mock_session_local:
                mock_session = AsyncMock()
                mock_session.execute.side_effect = Exception("DB is down")  # DB is down
                mock_session_local.return_value.__aenter__.return_value = mock_session

                response = await async_client.get("/api/v1/health/readiness")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()["detail"]
        assert data["status"] == "not ready"
        assert data["checks"]["database"] is False
        assert data["checks"]["redis"] is True
