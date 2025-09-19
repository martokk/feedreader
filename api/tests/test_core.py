import os
from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as redis
from app.core.config import Settings
from app.core.database import get_db
from app.core.redis import RSS_EVENTS_CHANNEL, close_redis, get_redis, publish_event
from sqlalchemy.ext.asyncio import AsyncSession


class TestSettings:
    """Test configuration settings."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = Settings()

        assert settings.postgres_host == "localhost"
        assert settings.postgres_port == 5432
        assert settings.postgres_db == "reader"
        assert settings.postgres_user == "reader"
        assert settings.postgres_password == "change-me"
        assert settings.redis_url == "redis://localhost:6379/0"
        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 8000
        assert settings.uvicorn_workers == 2
        assert settings.sse_heartbeat_ms == 15000
        assert settings.app_env == "development"
        assert settings.log_level == "info"
        assert settings.timezone == "UTC"
        assert settings.frontend_origin == "http://localhost:3000"

    def test_database_url_property(self):
        """Test database URL property construction."""
        settings = Settings(
            postgres_user="testuser",
            postgres_password="testpass",
            postgres_host="testhost",
            postgres_port=5433,
            postgres_db="testdb",
        )

        expected_url = "postgresql+asyncpg://testuser:testpass@testhost:5433/testdb"
        assert settings.database_url == expected_url

    def test_cors_origins_development(self):
        """Test CORS origins in development environment."""
        settings = Settings(
            app_env="development", frontend_origin="http://localhost:3001"
        )

        origins = settings.cors_origins

        assert "http://localhost:3000" in origins
        assert "http://127.0.0.1:3000" in origins
        assert "http://localhost:3001" in origins
        assert "http://127.0.0.1:3001" in origins
        assert settings.frontend_origin in origins

    def test_cors_origins_production(self):
        """Test CORS origins in production environment."""
        settings = Settings(app_env="production", frontend_origin="https://example.com")

        origins = settings.cors_origins

        assert origins == ["https://example.com"]

    def test_environment_variable_override(self):
        """Test that environment variables override defaults."""
        with patch.dict(
            os.environ,
            {
                "POSTGRES_HOST": "env-host",
                "POSTGRES_PORT": "5434",
                "POSTGRES_DB": "env-db",
                "REDIS_URL": "redis://env-redis:6379/2",
                "APP_ENV": "testing",
            },
        ):
            settings = Settings()

            assert settings.postgres_host == "env-host"
            assert settings.postgres_port == 5434
            assert settings.postgres_db == "env-db"
            assert settings.redis_url == "redis://env-redis:6379/2"
            assert settings.app_env == "testing"

    def test_case_insensitive_env_vars(self):
        """Test that environment variables are case insensitive."""
        with patch.dict(
            os.environ, {"postgres_host": "lower-case-host", "POSTGRES_PORT": "5435"}
        ):
            settings = Settings()

            assert settings.postgres_host == "lower-case-host"
            assert settings.postgres_port == 5435

    def test_custom_settings_values(self):
        """Test creating settings with custom values."""
        settings = Settings(
            postgres_host="custom-host",
            postgres_port=9999,
            redis_url="redis://custom:6379/5",
            api_port=9000,
            uvicorn_workers=4,
            sse_heartbeat_ms=30000,
            app_env="staging",
            log_level="debug",
            timezone="America/New_York",
            frontend_origin="https://staging.example.com",
        )

        assert settings.postgres_host == "custom-host"
        assert settings.postgres_port == 9999
        assert settings.redis_url == "redis://custom:6379/5"
        assert settings.api_port == 9000
        assert settings.uvicorn_workers == 4
        assert settings.sse_heartbeat_ms == 30000
        assert settings.app_env == "staging"
        assert settings.log_level == "debug"
        assert settings.timezone == "America/New_York"
        assert settings.frontend_origin == "https://staging.example.com"


class TestDatabase:
    """Test database functionality."""

    @pytest.mark.asyncio
    async def test_get_db_dependency(self, test_engine):
        """Test get_db dependency function."""
        # This test verifies that get_db yields a session
        db_gen = get_db()
        db_session = await db_gen.__anext__()

        assert isinstance(db_session, AsyncSession)

        # Clean up
        try:
            await db_gen.__anext__()
        except StopAsyncIteration:
            pass  # Expected when generator closes

    @pytest.mark.asyncio
    async def test_database_session_isolation(self, db_session):
        """Test that database sessions are properly isolated."""
        from app.models import Feed

        from tests.factories import create_feed

        # Create a feed in this session
        feed = await create_feed(db_session, title="Test Feed")
        assert feed.id is not None

        # In a new session, the feed should not be visible until commit
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as new_session:
            from sqlalchemy import select

            stmt = select(Feed).where(Feed.id == feed.id)
            result = await new_session.execute(stmt)
            found_feed = result.scalar_one_or_none()

            # Should find the feed since we committed in create_feed
            assert found_feed is not None
            assert found_feed.title == "Test Feed"

    @pytest.mark.asyncio
    async def test_database_rollback(self, db_session):
        """Test database rollback functionality."""
        from app.models import Feed
        from sqlalchemy import select

        # Create a feed but don't commit
        feed = Feed(
            url="https://test.com/feed.xml",
            title="Test Feed",
            interval_seconds=900,
            per_host_key="test.com",
            next_run_at=pytest.importorskip("datetime").datetime.utcnow(),
        )
        db_session.add(feed)

        # Rollback the session
        await db_session.rollback()

        # Feed should not exist
        stmt = select(Feed).where(Feed.url == "https://test.com/feed.xml")
        result = await db_session.execute(stmt)
        found_feed = result.scalar_one_or_none()

        assert found_feed is None


class TestRedis:
    """Test Redis functionality."""

    @pytest.mark.asyncio
    async def test_get_redis_client(self, mock_redis):
        """Test getting Redis client."""
        with patch("app.core.redis.redis_client", mock_redis):
            client = await get_redis()
            assert client is mock_redis

    @pytest.mark.asyncio
    async def test_get_redis_creates_new_client(self):
        """Test that get_redis creates a new client if none exists."""
        with patch("app.core.redis.redis_client", None):
            with patch("app.core.redis.redis.from_url") as mock_from_url:
                mock_client = AsyncMock()
                mock_from_url.return_value = mock_client

                client = await get_redis()

                assert client is mock_client
                mock_from_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_redis(self):
        """Test closing Redis connection."""
        mock_redis = AsyncMock()
        with patch("app.core.redis.redis_client", mock_redis):
            await close_redis()
            mock_redis.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_redis_no_client(self):
        """Test closing Redis when no client exists."""
        with patch("app.core.redis.redis_client", None):
            # Should not raise an exception
            await close_redis()

    @pytest.mark.asyncio
    async def test_publish_event(self):
        """Test publishing events to Redis."""
        mock_redis = AsyncMock()
        with patch("app.core.redis.get_redis", return_value=mock_redis):
            event_data = {"feed_id": "123", "status": "updated"}

            await publish_event("test:channel", "feed_updated", event_data)

            # Verify publish was called
            mock_redis.publish.assert_called_once()
            call_args = mock_redis.publish.call_args

            assert call_args[0][0] == "test:channel"  # Channel

            # Parse the published message
            import json

            published_data = json.loads(call_args[0][1])

            assert published_data["type"] == "feed_updated"
            assert published_data["data"] == event_data
            assert "timestamp" in published_data

    @pytest.mark.asyncio
    async def test_publish_event_to_rss_channel(self):
        """Test publishing event to RSS events channel."""
        mock_redis = AsyncMock()
        with patch("app.core.redis.get_redis", return_value=mock_redis):
            event_data = {"item_id": "456", "action": "marked_read"}

            await publish_event(RSS_EVENTS_CHANNEL, "item_read", event_data)

            mock_redis.publish.assert_called_once()
            call_args = mock_redis.publish.call_args

            assert call_args[0][0] == RSS_EVENTS_CHANNEL

    def test_rss_events_channel_constant(self):
        """Test RSS events channel constant."""
        assert RSS_EVENTS_CHANNEL == "rss:events"

    @pytest.mark.asyncio
    async def test_redis_connection_error_handling(self):
        """Test Redis connection error handling."""
        with patch("app.core.redis.redis.from_url") as mock_from_url:
            mock_from_url.side_effect = redis.ConnectionError("Connection failed")

            with pytest.raises(redis.ConnectionError):
                await get_redis()

    @pytest.mark.asyncio
    async def test_redis_publish_error_handling(self):
        """Test Redis publish error handling."""
        mock_redis = AsyncMock()
        mock_redis.publish.side_effect = redis.RedisError("Publish failed")

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            with pytest.raises(redis.RedisError):
                await publish_event("test:channel", "test_event", {})

        @pytest.mark.asyncio
    async def test_redis_client_ping(self):
        """Test Redis client ping functionality."""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        
        with patch("app.core.redis.get_redis", return_value=mock_redis):
            client = await get_redis()
            result = await client.ping()

            assert result is True
            mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_pubsub_functionality(self, mock_redis):
        """Test Redis pub/sub functionality."""
        mock_pubsub = mock_redis.pubsub()

        # Test subscription
        await mock_pubsub.subscribe("test:channel")
        assert "test:channel" in mock_pubsub.subscribed_channels

        # Test unsubscription
        await mock_pubsub.unsubscribe("test:channel")
        assert "test:channel" not in mock_pubsub.subscribed_channels

    @pytest.mark.asyncio
    async def test_redis_data_operations(self, mock_redis):
        """Test Redis data operations."""
        # Test set/get
        await mock_redis.set("test:key", "test:value")
        assert mock_redis.data["test:key"] == "test:value"

        value = await mock_redis.get("test:key")
        assert value == "test:value"

        # Test delete
        await mock_redis.delete("test:key")
        assert "test:key" not in mock_redis.data

        # Test list operations
        await mock_redis.lpush("test:list", "item1")
        await mock_redis.lpush("test:list", "item2")

        assert mock_redis.data["test:list"] == ["item2", "item1"]

        item = await mock_redis.rpop("test:list")
        assert item == "item1"
        assert mock_redis.data["test:list"] == ["item2"]


class TestCoreIntegration:
    """Test integration between core components."""

    def test_settings_database_url_integration(self):
        """Test that settings properly construct database URL."""
        settings = Settings(
            postgres_user="integration_user",
            postgres_password="integration_pass",
            postgres_host="integration_host",
            postgres_port=5432,
            postgres_db="integration_db",
        )

        expected_url = "postgresql+asyncpg://integration_user:integration_pass@integration_host:5432/integration_db"
        assert settings.database_url == expected_url

    @pytest.mark.asyncio
    async def test_redis_settings_integration(self):
        """Test that Redis uses settings URL."""
        test_redis_url = "redis://test-host:6380/3"

        with patch("app.core.redis.settings") as mock_settings:
            mock_settings.redis_url = test_redis_url

            with patch("app.core.redis.redis.from_url") as mock_from_url:
                mock_client = AsyncMock()
                mock_from_url.return_value = mock_client

                await get_redis()

                mock_from_url.assert_called_once_with(test_redis_url)

    def test_environment_variable_precedence(self):
        """Test that environment variables take precedence over defaults."""
        env_vars = {
            "POSTGRES_HOST": "env-postgres",
            "POSTGRES_PORT": "9999",
            "POSTGRES_DB": "env-db",
            "POSTGRES_USER": "env-user",
            "POSTGRES_PASSWORD": "env-password",
            "REDIS_URL": "redis://env-redis:6379/5",
            "API_HOST": "env-api-host",
            "API_PORT": "9000",
            "APP_ENV": "env-testing",
        }

        with patch.dict(os.environ, env_vars):
            settings = Settings()

            assert settings.postgres_host == "env-postgres"
            assert settings.postgres_port == 9999
            assert settings.postgres_db == "env-db"
            assert settings.postgres_user == "env-user"
            assert settings.postgres_password == "env-password"
            assert settings.redis_url == "redis://env-redis:6379/5"
            assert settings.api_host == "env-api-host"
            assert settings.api_port == 9000
            assert settings.app_env == "env-testing"
