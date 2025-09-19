import uuid
from datetime import datetime

import pytest
from app.schemas.feed import (
    FeedCreate,
    FeedResponse,
    FeedStats,
    FeedUpdate,
    FeedValidation,
)
from app.schemas.item import ItemDetail, ItemResponse
from app.schemas.read_state import ReadStateUpdate
from pydantic import ValidationError


class TestFeedSchemas:
    """Test feed-related schemas."""

    def test_feed_create_valid(self):
        """Test valid feed creation data."""
        data = {
            "url": "https://example.com/feed.xml",
            "title": "Test Feed",
            "interval_seconds": 900,
        }

        feed_create = FeedCreate(**data)

        assert feed_create.url == data["url"]
        assert feed_create.title == data["title"]
        assert feed_create.interval_seconds == data["interval_seconds"]

    def test_feed_create_minimal(self):
        """Test feed creation with minimal data."""
        data = {"url": "https://example.com/feed.xml"}

        feed_create = FeedCreate(**data)

        assert feed_create.url == data["url"]
        assert feed_create.title is None
        assert feed_create.interval_seconds == 900  # Default value

    def test_feed_create_invalid_url(self):
        """Test feed creation with invalid URL."""
        data = {"url": "not-a-url"}

        with pytest.raises(ValidationError) as exc_info:
            FeedCreate(**data)

        assert "URL must start with http://" in str(exc_info.value)

    def test_feed_create_url_validation(self):
        """Test various URL validation scenarios."""
        # Valid URLs
        valid_urls = [
            "http://example.com/feed.xml",
            "https://example.com/feed.xml",
            "https://subdomain.example.com/path/to/feed",
            "http://localhost:8080/feed",
        ]

        for url in valid_urls:
            feed_create = FeedCreate(url=url)
            assert feed_create.url == url

        # Invalid URLs
        invalid_urls = [
            "ftp://example.com/feed.xml",
            "example.com/feed.xml",
            "//example.com/feed.xml",
            "",
        ]

        for url in invalid_urls:
            with pytest.raises(ValidationError):
                FeedCreate(url=url)

    def test_feed_update_valid(self):
        """Test valid feed update data."""
        data = {"title": "Updated Feed Title", "interval_seconds": 1800}

        feed_update = FeedUpdate(**data)

        assert feed_update.title == data["title"]
        assert feed_update.interval_seconds == data["interval_seconds"]

    def test_feed_update_partial(self):
        """Test partial feed update."""
        data = {"title": "Updated Title Only"}

        feed_update = FeedUpdate(**data)

        assert feed_update.title == data["title"]
        assert feed_update.interval_seconds is None

    def test_feed_update_interval_validation(self):
        """Test feed update interval validation."""
        # Valid intervals
        valid_intervals = [60, 300, 900, 3600]

        for interval in valid_intervals:
            feed_update = FeedUpdate(interval_seconds=interval)
            assert feed_update.interval_seconds == interval

        # Invalid intervals
        invalid_intervals = [0, 30, 59, -100]

        for interval in invalid_intervals:
            with pytest.raises(ValidationError) as exc_info:
                FeedUpdate(interval_seconds=interval)
            assert "must be at least 60 seconds" in str(exc_info.value)

    def test_feed_stats_valid(self):
        """Test valid feed stats data."""
        feed_id = uuid.uuid4()
        now = datetime.utcnow()

        data = {
            "feed_id": feed_id,
            "total_items": 100,
            "unread_items": 25,
            "last_fetch_at": now,
            "last_fetch_status": 200,
            "next_run_at": now,
        }

        feed_stats = FeedStats(**data)

        assert feed_stats.feed_id == feed_id
        assert feed_stats.total_items == 100
        assert feed_stats.unread_items == 25
        assert feed_stats.last_fetch_at == now
        assert feed_stats.last_fetch_status == 200
        assert feed_stats.next_run_at == now

    def test_feed_validation_valid(self):
        """Test valid feed validation response."""
        data = {
            "url": "https://example.com/feed.xml",
            "is_valid": True,
            "feed_title": "Example Feed",
        }

        validation = FeedValidation(**data)

        assert validation.url == data["url"]
        assert validation.is_valid is True
        assert validation.feed_title == data["feed_title"]
        assert validation.error_message is None

    def test_feed_validation_invalid(self):
        """Test invalid feed validation response."""
        data = {
            "url": "https://example.com/invalid-feed.xml",
            "is_valid": False,
            "error_message": "Feed parsing error",
        }

        validation = FeedValidation(**data)

        assert validation.url == data["url"]
        assert validation.is_valid is False
        assert validation.feed_title is None
        assert validation.error_message == data["error_message"]

    def test_feed_response_valid(self):
        """Test valid feed response data."""
        feed_id = uuid.uuid4()
        now = datetime.utcnow()

        data = {
            "id": feed_id,
            "url": "https://example.com/feed.xml",
            "title": "Test Feed",
            "last_fetch_at": now,
            "last_status": 200,
            "next_run_at": now,
            "interval_seconds": 900,
            "created_at": now,
            "updated_at": now,
        }

        feed_response = FeedResponse(**data)

        assert feed_response.id == feed_id
        assert feed_response.url == data["url"]
        assert feed_response.title == data["title"]
        assert feed_response.last_fetch_at == now
        assert feed_response.last_status == 200
        assert feed_response.next_run_at == now
        assert feed_response.interval_seconds == 900


class TestItemSchemas:
    """Test item-related schemas."""

    def test_item_response_valid(self):
        """Test valid item response data."""
        item_id = uuid.uuid4()
        feed_id = uuid.uuid4()
        now = datetime.utcnow()

        data = {
            "id": item_id,
            "feed_id": feed_id,
            "title": "Test Item",
            "url": "https://example.com/item/123",
            "published_at": now,
            "fetched_at": now,
            "created_at": now,
            "is_read": True,
            "starred": False,
        }

        item_response = ItemResponse(**data)

        assert item_response.id == item_id
        assert item_response.feed_id == feed_id
        assert item_response.title == data["title"]
        assert item_response.url == data["url"]
        assert item_response.published_at == now
        assert item_response.is_read is True
        assert item_response.starred is False

    def test_item_response_minimal(self):
        """Test item response with minimal data."""
        item_id = uuid.uuid4()
        feed_id = uuid.uuid4()
        now = datetime.utcnow()

        data = {
            "id": item_id,
            "feed_id": feed_id,
            "title": None,
            "url": None,
            "published_at": None,
            "fetched_at": now,
            "created_at": now,
        }

        item_response = ItemResponse(**data)

        assert item_response.id == item_id
        assert item_response.feed_id == feed_id
        assert item_response.title is None
        assert item_response.url is None
        assert item_response.published_at is None
        assert item_response.is_read is None
        assert item_response.starred is None

    def test_item_detail_valid(self):
        """Test valid item detail data."""
        item_id = uuid.uuid4()
        feed_id = uuid.uuid4()
        now = datetime.utcnow()

        data = {
            "id": item_id,
            "feed_id": feed_id,
            "title": "Test Item",
            "url": "https://example.com/item/123",
            "content_html": "<p>Test content</p>",
            "content_text": "Test content",
            "published_at": now,
            "fetched_at": now,
            "created_at": now,
            "is_read": False,
            "starred": True,
        }

        item_detail = ItemDetail(**data)

        assert item_detail.id == item_id
        assert item_detail.feed_id == feed_id
        assert item_detail.title == data["title"]
        assert item_detail.url == data["url"]
        assert item_detail.content_html == data["content_html"]
        assert item_detail.content_text == data["content_text"]
        assert item_detail.published_at == now
        assert item_detail.is_read is False
        assert item_detail.starred is True

    def test_item_detail_no_content(self):
        """Test item detail without content."""
        item_id = uuid.uuid4()
        feed_id = uuid.uuid4()
        now = datetime.utcnow()

        data = {
            "id": item_id,
            "feed_id": feed_id,
            "title": "Test Item",
            "url": None,
            "content_html": None,
            "content_text": None,
            "published_at": None,
            "fetched_at": now,
            "created_at": now,
        }

        item_detail = ItemDetail(**data)

        assert item_detail.content_html is None
        assert item_detail.content_text is None


class TestReadStateSchemas:
    """Test read state schemas."""

    def test_read_state_update_valid(self):
        """Test valid read state update data."""
        data = {"read": True, "starred": False}

        update = ReadStateUpdate(**data)

        assert update.read is True
        assert update.starred is False

    def test_read_state_update_partial(self):
        """Test partial read state update."""
        # Only read status
        update1 = ReadStateUpdate(read=True)
        assert update1.read is True
        assert update1.starred is None

        # Only starred status
        update2 = ReadStateUpdate(starred=True)
        assert update2.read is None
        assert update2.starred is True

        # Empty update
        update3 = ReadStateUpdate()
        assert update3.read is None
        assert update3.starred is None

    def test_read_state_update_mark_unread(self):
        """Test marking item as unread."""
        update = ReadStateUpdate(read=False)
        assert update.read is False

    def test_read_state_update_toggle_starred(self):
        """Test toggling starred status."""
        # Star item
        update1 = ReadStateUpdate(starred=True)
        assert update1.starred is True

        # Unstar item
        update2 = ReadStateUpdate(starred=False)
        assert update2.starred is False


class TestSchemaValidation:
    """Test schema validation edge cases."""

    def test_uuid_validation(self):
        """Test UUID field validation."""
        valid_uuid = uuid.uuid4()

        # Valid UUID
        item_response = ItemResponse(
            id=valid_uuid,
            feed_id=valid_uuid,
            title=None,
            url=None,
            published_at=None,
            fetched_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        assert item_response.id == valid_uuid

        # Invalid UUID string
        with pytest.raises(ValidationError):
            ItemResponse(
                id="not-a-uuid",
                feed_id=valid_uuid,
                fetched_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
            )

    def test_datetime_validation(self):
        """Test datetime field validation."""
        item_id = uuid.uuid4()
        feed_id = uuid.uuid4()
        now = datetime.utcnow()

        # Valid datetime
        item_response = ItemResponse(
            id=item_id,
            feed_id=feed_id,
            title=None,
            url=None,
            published_at=None,
            fetched_at=now,
            created_at=now,
        )
        assert item_response.fetched_at == now

        # Invalid datetime string
        with pytest.raises(ValidationError):
            ItemResponse(
                id=item_id, feed_id=feed_id, fetched_at="not-a-datetime", created_at=now
            )

    def test_optional_fields(self):
        """Test handling of optional fields."""
        feed_id = uuid.uuid4()
        now = datetime.utcnow()

        # With optional fields
        feed_stats = FeedStats(
            feed_id=feed_id,
            total_items=10,
            unread_items=5,
            last_fetch_at=now,
            last_fetch_status=200,
            next_run_at=now,
        )
        assert feed_stats.last_fetch_at == now
        assert feed_stats.last_fetch_status == 200

        # Without optional fields
        feed_stats = FeedStats(
            feed_id=feed_id,
            total_items=10,
            unread_items=5,
            last_fetch_at=None,
            last_fetch_status=None,
            next_run_at=now,
        )
        assert feed_stats.last_fetch_at is None
        assert feed_stats.last_fetch_status is None

    def test_schema_serialization(self):
        """Test schema serialization to dict."""
        data = {
            "url": "https://example.com/feed.xml",
            "title": "Test Feed",
            "interval_seconds": 900,
        }

        feed_create = FeedCreate(**data)
        serialized = feed_create.dict()

        assert serialized == data

        # Test exclude_unset for partial updates
        feed_update = FeedUpdate(title="New Title")
        serialized = feed_update.dict(exclude_unset=True)

        assert serialized == {"title": "New Title"}
        assert "interval_seconds" not in serialized
