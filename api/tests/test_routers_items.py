import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import status

from tests.factories import (
    create_feed,
    create_feed_with_items,
    create_item,
    create_read_state,
)


class TestItemsRouter:
    """Test items router endpoints."""

    @pytest.mark.asyncio
    async def test_get_feed_items(self, async_client, db_session):
        """Test getting items for a specific feed."""
        # Create feed with items
        feed, items, read_states = await create_feed_with_items(
            db_session, num_items=3, num_read=1
        )

        response = await async_client.get(f"/api/v1/feeds/{feed.id}/items")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

        # Check response structure
        for item_data in data:
            assert "id" in item_data
            assert "feed_id" in item_data
            assert "title" in item_data
            assert "url" in item_data
            assert "published_at" in item_data
            assert "fetched_at" in item_data
            assert "created_at" in item_data
            assert "is_read" in item_data
            assert "starred" in item_data

    @pytest.mark.asyncio
    async def test_get_feed_items_pagination(self, async_client, db_session):
        """Test items pagination."""
        # Create feed with many items
        feed = await create_feed(db_session)
        for i in range(10):
            await create_item(db_session, feed_id=feed.id, title=f"Item {i}")

        # Test with limit
        response = await async_client.get(f"/api/v1/feeds/{feed.id}/items?limit=5")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 5

        # Test with skip and limit
        response = await async_client.get(
            f"/api/v1/feeds/{feed.id}/items?skip=3&limit=4"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 4

    @pytest.mark.asyncio
    async def test_get_feed_items_unread_only(self, async_client, db_session):
        """Test getting only unread items."""
        # Create feed with items, some read
        feed, items, read_states = await create_feed_with_items(
            db_session, num_items=5, num_read=2
        )

        response = await async_client.get(
            f"/api/v1/feeds/{feed.id}/items?unread_only=true"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3  # 5 total - 2 read = 3 unread

        # All returned items should be unread
        for item_data in data:
            assert item_data["is_read"] is False

    @pytest.mark.asyncio
    async def test_get_feed_items_date_filters(self, async_client, db_session):
        """Test filtering items by date."""
        feed = await create_feed(db_session)
        now = datetime.utcnow()

        # Create items with different published dates
        item1 = await create_item(
            db_session,
            feed_id=feed.id,
            published_at=now - timedelta(days=2),
            title="Old Item",
        )
        item2 = await create_item(
            db_session,
            feed_id=feed.id,
            published_at=now - timedelta(hours=1),
            title="Recent Item",
        )
        item3 = await create_item(
            db_session,
            feed_id=feed.id,
            published_at=now + timedelta(hours=1),
            title="Future Item",
        )

        # Test since filter
        since_date = (now - timedelta(days=1)).isoformat()
        response = await async_client.get(
            f"/api/v1/feeds/{feed.id}/items?since={since_date}"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2  # Recent and Future items

        # Test until filter
        until_date = (now - timedelta(hours=30)).isoformat()
        response = await async_client.get(
            f"/api/v1/feeds/{feed.id}/items?until={until_date}"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1  # Only old item

    @pytest.mark.asyncio
    async def test_get_feed_items_not_found(self, async_client):
        """Test getting items for non-existent feed."""
        fake_id = uuid.uuid4()
        response = await async_client.get(f"/api/v1/feeds/{fake_id}/items")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 0  # Empty list for non-existent feed

    @pytest.mark.asyncio
    async def test_get_feed_items_ordering(self, async_client, db_session):
        """Test that items are ordered by published_at desc, then created_at desc."""
        feed = await create_feed(db_session)
        now = datetime.utcnow()

        # Create items with different timestamps
        item1 = await create_item(
            db_session,
            feed_id=feed.id,
            title="Oldest",
            published_at=now - timedelta(hours=3),
        )
        item2 = await create_item(
            db_session,
            feed_id=feed.id,
            title="Newest",
            published_at=now - timedelta(hours=1),
        )
        item3 = await create_item(
            db_session,
            feed_id=feed.id,
            title="Middle",
            published_at=now - timedelta(hours=2),
        )

        response = await async_client.get(f"/api/v1/feeds/{feed.id}/items")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

        # Should be ordered newest first
        assert data[0]["title"] == "Newest"
        assert data[1]["title"] == "Middle"
        assert data[2]["title"] == "Oldest"

    @pytest.mark.asyncio
    async def test_get_item_detail(self, async_client, db_session):
        """Test getting full item details."""
        feed = await create_feed(db_session)
        item = await create_item(
            db_session,
            feed_id=feed.id,
            title="Test Item",
            content_html="<p>Test content</p>",
            content_text="Test content",
        )

        response = await async_client.get(f"/api/v1/feeds/items/{item.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(item.id)
        assert data["feed_id"] == str(feed.id)
        assert data["title"] == "Test Item"
        assert data["content_html"] == "<p>Test content</p>"
        assert data["content_text"] == "Test content"
        assert data["is_read"] is False
        assert data["starred"] is False

    @pytest.mark.asyncio
    async def test_get_item_detail_with_read_state(self, async_client, db_session):
        """Test getting item details with read state."""
        feed = await create_feed(db_session)
        item = await create_item(db_session, feed_id=feed.id)
        read_state = await create_read_state(
            db_session, item_id=item.id, read_at=datetime.utcnow(), starred=True
        )

        response = await async_client.get(f"/api/v1/feeds/items/{item.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_read"] is True
        assert data["starred"] is True

    @pytest.mark.asyncio
    async def test_get_item_detail_not_found(self, async_client):
        """Test getting non-existent item."""
        fake_id = uuid.uuid4()
        response = await async_client.get(f"/api/v1/feeds/items/{fake_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["detail"] == "Item not found"

    @pytest.mark.asyncio
    async def test_update_item_read_status(self, async_client, db_session):
        """Test updating item read status."""
        feed = await create_feed(db_session)
        item = await create_item(db_session, feed_id=feed.id)

        # Mark as read
        update_data = {"read": True}
        response = await async_client.post(
            f"/api/v1/feeds/items/{item.id}/read", json=update_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "updated"

        # Verify item is marked as read
        detail_response = await async_client.get(f"/api/v1/feeds/items/{item.id}")
        detail_data = detail_response.json()
        assert detail_data["is_read"] is True

    @pytest.mark.asyncio
    async def test_update_item_starred_status(self, async_client, db_session):
        """Test updating item starred status."""
        feed = await create_feed(db_session)
        item = await create_item(db_session, feed_id=feed.id)

        # Mark as starred
        update_data = {"starred": True}
        response = await async_client.post(
            f"/api/v1/feeds/items/{item.id}/read", json=update_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "updated"

        # Verify item is starred
        detail_response = await async_client.get(f"/api/v1/feeds/items/{item.id}")
        detail_data = detail_response.json()
        assert detail_data["starred"] is True

    @pytest.mark.asyncio
    async def test_update_item_mark_unread(self, async_client, db_session):
        """Test marking item as unread."""
        feed = await create_feed(db_session)
        item = await create_item(db_session, feed_id=feed.id)

        # First mark as read
        read_state = await create_read_state(
            db_session, item_id=item.id, read_at=datetime.utcnow()
        )

        # Then mark as unread
        update_data = {"read": False}
        response = await async_client.post(
            f"/api/v1/feeds/items/{item.id}/read", json=update_data
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify item is unread
        detail_response = await async_client.get(f"/api/v1/feeds/items/{item.id}")
        detail_data = detail_response.json()
        assert detail_data["is_read"] is False

    @pytest.mark.asyncio
    async def test_update_item_read_status_not_found(self, async_client):
        """Test updating read status for non-existent item."""
        fake_id = uuid.uuid4()
        update_data = {"read": True}

        response = await async_client.post(
            f"/api/v1/feeds/items/{fake_id}/read", json=update_data
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["detail"] == "Item not found"

    @pytest.mark.asyncio
    async def test_update_item_empty_update(self, async_client, db_session):
        """Test updating item with empty data."""
        feed = await create_feed(db_session)
        item = await create_item(db_session, feed_id=feed.id)

        # Empty update should be valid
        update_data = {}
        response = await async_client.post(
            f"/api/v1/feeds/items/{item.id}/read", json=update_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "updated"

    @pytest.mark.asyncio
    async def test_update_item_both_read_and_starred(self, async_client, db_session):
        """Test updating both read and starred status."""
        feed = await create_feed(db_session)
        item = await create_item(db_session, feed_id=feed.id)

        # Update both fields
        update_data = {"read": True, "starred": True}
        response = await async_client.post(
            f"/api/v1/feeds/items/{item.id}/read", json=update_data
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify both fields are updated
        detail_response = await async_client.get(f"/api/v1/feeds/items/{item.id}")
        detail_data = detail_response.json()
        assert detail_data["is_read"] is True
        assert detail_data["starred"] is True

    @pytest.mark.asyncio
    async def test_get_feed_items_read_state_consistency(
        self, async_client, db_session
    ):
        """Test that read state is consistent across endpoints."""
        feed = await create_feed(db_session)
        item = await create_item(db_session, feed_id=feed.id)

        # Mark as read and starred
        update_data = {"read": True, "starred": True}
        await async_client.post(f"/api/v1/feeds/items/{item.id}/read", json=update_data)

        # Check in feed items list
        feed_items_response = await async_client.get(f"/api/v1/feeds/{feed.id}/items")
        feed_items_data = feed_items_response.json()
        assert len(feed_items_data) == 1
        assert feed_items_data[0]["is_read"] is True
        assert feed_items_data[0]["starred"] is True

        # Check in item detail
        item_detail_response = await async_client.get(f"/api/v1/feeds/items/{item.id}")
        item_detail_data = item_detail_response.json()
        assert item_detail_data["is_read"] is True
        assert item_detail_data["starred"] is True

    @pytest.mark.asyncio
    async def test_get_feed_items_mixed_read_states(self, async_client, db_session):
        """Test getting items with mixed read states."""
        feed = await create_feed(db_session)

        # Create items with different read states
        unread_item = await create_item(db_session, feed_id=feed.id, title="Unread")
        read_item = await create_item(db_session, feed_id=feed.id, title="Read")
        starred_item = await create_item(db_session, feed_id=feed.id, title="Starred")

        # Set read states
        await create_read_state(
            db_session, item_id=read_item.id, read_at=datetime.utcnow()
        )
        await create_read_state(db_session, item_id=starred_item.id, starred=True)

        response = await async_client.get(f"/api/v1/feeds/{feed.id}/items")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

        # Find each item in response
        items_by_title = {item["title"]: item for item in data}

        assert items_by_title["Unread"]["is_read"] is False
        assert items_by_title["Unread"]["starred"] is False

        assert items_by_title["Read"]["is_read"] is True
        assert items_by_title["Read"]["starred"] is False

        assert items_by_title["Starred"]["is_read"] is False
        assert items_by_title["Starred"]["starred"] is True

    @pytest.mark.asyncio
    async def test_item_read_state_creation(self, async_client, db_session):
        """Test that read state is created when updating non-existent read state."""
        feed = await create_feed(db_session)
        item = await create_item(db_session, feed_id=feed.id)

        # Item should have no read state initially
        detail_response = await async_client.get(f"/api/v1/feeds/items/{item.id}")
        detail_data = detail_response.json()
        assert detail_data["is_read"] is False
        assert detail_data["starred"] is False

        # Update read status (should create read state)
        update_data = {"read": True}
        response = await async_client.post(
            f"/api/v1/feeds/items/{item.id}/read", json=update_data
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify read state was created
        detail_response = await async_client.get(f"/api/v1/feeds/items/{item.id}")
        detail_data = detail_response.json()
        assert detail_data["is_read"] is True

    @pytest.mark.asyncio
    async def test_get_items_with_null_published_date(self, async_client, db_session):
        """Test handling items with null published_at."""
        feed = await create_feed(db_session)
        item = await create_item(
            db_session, feed_id=feed.id, title="No Publish Date", published_at=None
        )

        response = await async_client.get(f"/api/v1/feeds/{feed.id}/items")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["published_at"] is None
        assert data[0]["title"] == "No Publish Date"

    @pytest.mark.asyncio
    async def test_invalid_uuid_handling(self, async_client):
        """Test handling of invalid UUIDs in URLs."""
        # Invalid feed ID
        response = await async_client.get("/api/v1/feeds/not-a-uuid/items")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Invalid item ID
        response = await async_client.get("/api/v1/feeds/items/not-a-uuid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Invalid item ID for read status update
        response = await async_client.post(
            "/api/v1/feeds/items/not-a-uuid/read", json={"read": True}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
