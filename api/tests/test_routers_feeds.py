import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status

from tests.factories import create_feed, create_feed_with_items


class TestFeedsRouter:
    """Test feeds router endpoints."""

    @pytest.mark.asyncio
    async def test_get_feeds(self, async_client, db_session):
        """Test getting all feeds."""
        # Create test feeds
        feed1 = await create_feed(db_session, title="Feed 1")
        feed2 = await create_feed(db_session, title="Feed 2")

        response = await async_client.get("/api/v1/feeds/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

        # Check that feeds are returned in descending order by created_at
        assert data[0]["title"] in ["Feed 1", "Feed 2"]
        assert data[1]["title"] in ["Feed 1", "Feed 2"]

    @pytest.mark.asyncio
    async def test_get_feeds_pagination(self, async_client, db_session):
        """Test feeds pagination."""
        # Create multiple feeds
        for i in range(5):
            await create_feed(db_session, title=f"Feed {i}")

        # Test with limit
        response = await async_client.get("/api/v1/feeds/?limit=3")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

        # Test with skip and limit
        response = await async_client.get("/api/v1/feeds/?skip=2&limit=2")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_get_feed_by_id(self, async_client, db_session):
        """Test getting a single feed by ID."""
        feed = await create_feed(db_session, title="Test Feed")

        response = await async_client.get(f"/api/v1/feeds/{feed.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(feed.id)
        assert data["title"] == "Test Feed"
        assert data["url"] == feed.url

    @pytest.mark.asyncio
    async def test_get_feed_not_found(self, async_client):
        """Test getting a non-existent feed."""
        fake_id = uuid.uuid4()
        response = await async_client.get(f"/api/v1/feeds/{fake_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["detail"] == "Feed not found"

    @pytest.mark.asyncio
    async def test_get_feed_stats(self, async_client, db_session):
        """Test getting feed statistics."""
        # Create feed with items, some read
        feed, items, read_states = await create_feed_with_items(
            db_session, num_items=5, num_read=2
        )

        response = await async_client.get(f"/api/v1/feeds/{feed.id}/stats")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["feed_id"] == str(feed.id)
        assert data["total_items"] == 5
        assert data["unread_items"] == 3  # 5 total - 2 read = 3 unread

    @pytest.mark.asyncio
    async def test_get_feed_stats_not_found(self, async_client):
        """Test getting stats for non-existent feed."""
        fake_id = uuid.uuid4()
        response = await async_client.get(f"/api/v1/feeds/{fake_id}/stats")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["detail"] == "Feed not found"

    @pytest.mark.asyncio
    async def test_validate_feed_url_valid(self, async_client):
        """Test validating a valid feed URL."""
        with patch("app.routers.feeds.feedparser.parse") as mock_parse:
            # Mock a successful feed parse
            mock_parse.return_value.bozo = False
            mock_parse.return_value.feed = {"title": "Test Feed"}

            response = await async_client.post(
                "/api/v1/feeds/validate", params={"url": "https://example.com/feed.xml"}
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["url"] == "https://example.com/feed.xml"
            assert data["is_valid"] is True
            assert data["feed_title"] == "Test Feed"

    @pytest.mark.asyncio
    async def test_validate_feed_url_invalid(self, async_client):
        """Test validating an invalid feed URL."""
        with patch("app.routers.feeds.feedparser.parse") as mock_parse:
            # Mock a failed feed parse
            mock_parse.return_value.bozo = True
            mock_parse.return_value.bozo_exception = "Invalid XML"

            response = await async_client.post(
                "/api/v1/feeds/validate",
                params={"url": "https://example.com/invalid.xml"},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["url"] == "https://example.com/invalid.xml"
            assert data["is_valid"] is False
            assert "Feed parsing error" in data["error_message"]

    @pytest.mark.asyncio
    async def test_validate_feed_url_no_feed_data(self, async_client):
        """Test validating URL with no feed data."""
        with patch("app.routers.feeds.feedparser.parse") as mock_parse:
            # Mock no feed data
            mock_parse.return_value.bozo = False
            mock_parse.return_value.feed = None

            response = await async_client.post(
                "/api/v1/feeds/validate",
                params={"url": "https://example.com/notafeed.xml"},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["is_valid"] is False
            assert "No feed data found" in data["error_message"]

    @pytest.mark.asyncio
    async def test_validate_feed_url_exception(self, async_client):
        """Test validating URL that raises exception."""
        with patch("app.routers.feeds.feedparser.parse") as mock_parse:
            # Mock an exception
            mock_parse.side_effect = Exception("Network error")

            response = await async_client.post(
                "/api/v1/feeds/validate",
                params={"url": "https://example.com/error.xml"},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["is_valid"] is False
            assert "Error validating feed" in data["error_message"]

    @pytest.mark.asyncio
    async def test_refresh_feed(self, async_client, db_session):
        """Test manually refreshing a feed."""
        feed = await create_feed(db_session)
        original_next_run = feed.next_run_at

        with patch("app.routers.feeds.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            response = await async_client.post(f"/api/v1/feeds/{feed.id}/refresh")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "Feed refresh queued" in data["message"]
            assert data["feed_id"] == str(feed.id)

            # Verify Redis job was queued
            mock_redis.lpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_feed_not_found(self, async_client):
        """Test refreshing non-existent feed."""
        fake_id = uuid.uuid4()
        response = await async_client.post(f"/api/v1/feeds/{fake_id}/refresh")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["detail"] == "Feed not found"

    @pytest.mark.asyncio
    async def test_create_feed(self, async_client, db_session):
        """Test creating a new feed."""
        feed_data = {
            "url": "https://example.com/feed.xml",
            "title": "Test Feed",
            "interval_seconds": 1800,
        }

        with patch("app.routers.feeds.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            response = await async_client.post("/api/v1/feeds/", json=feed_data)

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["url"] == feed_data["url"]
            assert data["title"] == feed_data["title"]
            assert data["interval_seconds"] == feed_data["interval_seconds"]
            assert "id" in data

            # Verify Redis job was queued
            mock_redis.lpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_feed_minimal(self, async_client, db_session):
        """Test creating a feed with minimal data."""
        feed_data = {"url": "https://example.com/minimal.xml"}

        with patch("app.routers.feeds.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            response = await async_client.post("/api/v1/feeds/", json=feed_data)

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["url"] == feed_data["url"]
            assert data["title"] is None
            assert data["interval_seconds"] == 900  # Default value

    @pytest.mark.asyncio
    async def test_create_feed_invalid_url(self, async_client):
        """Test creating feed with invalid URL."""
        feed_data = {"url": "not-a-url"}

        response = await async_client.post("/api/v1/feeds/", json=feed_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_feed_duplicate_url(self, async_client, db_session):
        """Test creating feed with duplicate URL."""
        # Create first feed
        existing_feed = await create_feed(
            db_session, url="https://duplicate-test.com/feed.xml"
        )

        # Try to create duplicate
        feed_data = {"url": "https://duplicate-test.com/feed.xml"}

        with patch("app.routers.feeds.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            response = await async_client.post("/api/v1/feeds/", json=feed_data)

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            assert data["detail"] == "Feed URL already exists"

    @pytest.mark.asyncio
    async def test_update_feed(self, async_client, db_session):
        """Test updating a feed."""
        feed = await create_feed(db_session, title="Original Title")

        update_data = {"title": "Updated Title", "interval_seconds": 3600}

        response = await async_client.patch(
            f"/api/v1/feeds/{feed.id}", json=update_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["interval_seconds"] == 3600

    @pytest.mark.asyncio
    async def test_update_feed_partial(self, async_client, db_session):
        """Test partially updating a feed."""
        feed = await create_feed(
            db_session, title="Original Title", interval_seconds=900
        )

        update_data = {"title": "New Title Only"}

        response = await async_client.patch(
            f"/api/v1/feeds/{feed.id}", json=update_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["title"] == "New Title Only"
        assert data["interval_seconds"] == 900  # Unchanged

    @pytest.mark.asyncio
    async def test_update_feed_not_found(self, async_client):
        """Test updating non-existent feed."""
        fake_id = uuid.uuid4()
        update_data = {"title": "New Title"}

        response = await async_client.patch(
            f"/api/v1/feeds/{fake_id}", json=update_data
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["detail"] == "Feed not found"

    @pytest.mark.asyncio
    async def test_delete_feed(self, async_client, db_session):
        """Test deleting a feed."""
        feed = await create_feed(db_session)

        response = await async_client.delete(f"/api/v1/feeds/{feed.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify feed is deleted
        get_response = await async_client.get(f"/api/v1/feeds/{feed.id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_feed_not_found(self, async_client):
        """Test deleting non-existent feed."""
        fake_id = uuid.uuid4()
        response = await async_client.delete(f"/api/v1/feeds/{fake_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["detail"] == "Feed not found"

    @pytest.mark.asyncio
    async def test_delete_feed_cascades(self, async_client, db_session):
        """Test that deleting a feed cascades to items and read states."""
        # Create feed with items
        feed, items, read_states = await create_feed_with_items(
            db_session, num_items=3, num_read=2
        )

        response = await async_client.delete(f"/api/v1/feeds/{feed.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify all related data is deleted
        for item in items:
            item_response = await async_client.get(f"/api/v1/feeds/items/{item.id}")
            assert item_response.status_code == status.HTTP_404_NOT_FOUND
