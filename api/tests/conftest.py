import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator

import httpx
import pytest
import pytest_asyncio
from app.core.config import Settings
from app.core.database import get_db
from app.main import app
from app.models import Base
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Test database URL - use SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


class TestSettings(Settings):
    """Test-specific settings."""

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "test_reader"
    postgres_user: str = "test"
    postgres_password: str = "test"
    redis_url: str = "redis://localhost:6379/1"  # Use different Redis DB for tests
    app_env: str = "testing"

    @property
    def database_url(self) -> str:
        return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session_maker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
def test_settings() -> TestSettings:
    """Get test settings."""
    return TestSettings()


@pytest.fixture
def override_get_db(db_session):
    """Override the get_db dependency."""

    async def _override_get_db():
        yield db_session

    return _override_get_db


@pytest.fixture
def test_client(override_get_db, test_settings) -> TestClient:
    """Create a test client."""
    app.dependency_overrides[get_db] = override_get_db

    # Override settings
    app.state.settings = test_settings

    with TestClient(app) as client:
        yield client

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(
    override_get_db, test_settings
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    app.dependency_overrides[get_db] = override_get_db
    app.state.settings = test_settings

    async with AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


# Mock Redis for tests
class MockRedis:
    def __init__(self):
        self.data = {}
        self.pubsub_channels = {}

    async def ping(self):
        return True

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value):
        self.data[key] = value

    async def delete(self, key):
        if key in self.data:
            del self.data[key]

    async def lpush(self, key, value):
        if key not in self.data:
            self.data[key] = []
        self.data[key].insert(0, value)

    async def rpop(self, key):
        if key in self.data and self.data[key]:
            return self.data[key].pop()
        return None

    async def publish(self, channel, message):
        if channel not in self.pubsub_channels:
            self.pubsub_channels[channel] = []
        self.pubsub_channels[channel].append(message)

    def pubsub(self):
        return MockPubSub(self)

    async def close(self):
        pass


class MockPubSub:
    def __init__(self, redis_mock):
        self.redis_mock = redis_mock
        self.subscribed_channels = []

    async def subscribe(self, channel):
        if channel not in self.subscribed_channels:
            self.subscribed_channels.append(channel)

    async def unsubscribe(self, channel):
        if channel in self.subscribed_channels:
            self.subscribed_channels.remove(channel)

    async def get_message(self, ignore_subscribe_messages=False):
        # Return None for timeout simulation
        return None

    async def close(self):
        pass


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    return MockRedis()


@pytest.fixture
def override_get_redis(mock_redis):
    """Override Redis dependency."""

    async def _override_get_redis():
        return mock_redis

    return _override_get_redis


# Sample data fixtures
@pytest.fixture
def sample_feed_data():
    """Sample feed data for testing."""
    return {
        "url": "https://example.com/feed.xml",
        "title": "Test Feed",
        "interval_seconds": 900,
    }


@pytest.fixture
def sample_feed_create_data():
    """Sample feed creation data."""
    return {
        "url": "https://test.example.com/rss.xml",
        "title": "Test RSS Feed",
        "interval_seconds": 1800,
    }


@pytest.fixture
def sample_item_data():
    """Sample item data for testing."""
    return {
        "guid": "test-guid-123",
        "title": "Test Item",
        "url": "https://example.com/item/123",
        "content_html": "<p>Test content</p>",
        "content_text": "Test content",
        "published_at": datetime.utcnow(),
        "fetched_at": datetime.utcnow(),
        "hash": "test-hash-123",
    }


@pytest.fixture
def future_datetime():
    """A datetime in the future."""
    return datetime.utcnow() + timedelta(hours=1)


@pytest.fixture
def past_datetime():
    """A datetime in the past."""
    return datetime.utcnow() - timedelta(hours=1)
