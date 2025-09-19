import uuid
from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status

from tests.factories import create_feed, create_item


class TestIntegrationWorkflows:
    """Test complete workflows across multiple components."""

    @pytest.mark.asyncio
    async def test_complete_feed_lifecycle(self, async_client, db_session):
        """Test complete feed lifecycle: create -> get -> update -> delete."""
        # Create feed
        feed_data = {
            "url": "https://integration-test.com/feed.xml",
            "title": "Integration Test Feed",
            "interval_seconds": 1800,
        }

        with patch("app.routers.feeds.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            # Create
            create_response = await async_client.post("/api/v1/feeds/", json=feed_data)
            assert create_response.status_code == status.HTTP_201_CREATED
            created_feed = create_response.json()
            feed_id = created_feed["id"]

            # Get
            get_response = await async_client.get(f"/api/v1/feeds/{feed_id}")
            assert get_response.status_code == status.HTTP_200_OK
            retrieved_feed = get_response.json()
            assert retrieved_feed["url"] == feed_data["url"]
            assert retrieved_feed["title"] == feed_data["title"]

            # Update
            update_data = {"title": "Updated Integration Feed"}
            update_response = await async_client.patch(
                f"/api/v1/feeds/{feed_id}", json=update_data
            )
            assert update_response.status_code == status.HTTP_200_OK
            updated_feed = update_response.json()
            assert updated_feed["title"] == "Updated Integration Feed"

            # Delete
            delete_response = await async_client.delete(f"/api/v1/feeds/{feed_id}")
            assert delete_response.status_code == status.HTTP_204_NO_CONTENT

            # Verify deletion
            get_deleted_response = await async_client.get(f"/api/v1/feeds/{feed_id}")
            assert get_deleted_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_feed_with_items_workflow(self, async_client, db_session):
        """Test workflow with feed items and read states."""
        # Create feed
        feed = await create_feed(db_session, title="Test Feed")

        # Create items for the feed
        item1 = await create_item(db_session, feed_id=feed.id, title="Item 1")
        item2 = await create_item(db_session, feed_id=feed.id, title="Item 2")
        item3 = await create_item(db_session, feed_id=feed.id, title="Item 3")

        # Get feed items
        items_response = await async_client.get(f"/api/v1/feeds/{feed.id}/items")
        assert items_response.status_code == status.HTTP_200_OK
        items_data = items_response.json()
        assert len(items_data) == 3

        # Mark one item as read
        read_update = {"read": True}
        read_response = await async_client.post(
            f"/api/v1/feeds/items/{item1.id}/read", json=read_update
        )
        assert read_response.status_code == status.HTTP_200_OK

        # Mark another item as starred
        star_update = {"starred": True}
        star_response = await async_client.post(
            f"/api/v1/feeds/items/{item2.id}/read", json=star_update
        )
        assert star_response.status_code == status.HTTP_200_OK

        # Get unread items only
        unread_response = await async_client.get(
            f"/api/v1/feeds/{feed.id}/items?unread_only=true"
        )
        assert unread_response.status_code == status.HTTP_200_OK
        unread_data = unread_response.json()
        assert len(unread_data) == 2  # item2 (starred but unread) and item3

        # Get item details
        detail_response = await async_client.get(f"/api/v1/feeds/items/{item1.id}")
        assert detail_response.status_code == status.HTTP_200_OK
        detail_data = detail_response.json()
        assert detail_data["is_read"] is True
        assert detail_data["starred"] is False

    @pytest.mark.asyncio
    async def test_opml_import_export_workflow(self, async_client, db_session):
        """Test OPML import followed by export workflow."""
        # Import OPML
        opml_content = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
    <head>
        <title>Test Import</title>
    </head>
    <body>
        <outline type="rss" text="Test Feed 1" xmlUrl="https://workflow1.com/feed.xml"/>
        <outline type="rss" text="Test Feed 2" xmlUrl="https://workflow2.com/feed.xml"/>
    </body>
</opml>"""

        with patch("app.routers.opml.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            # Import
            files = {
                "file": (
                    "import.opml",
                    BytesIO(opml_content.encode()),
                    "application/xml",
                )
            }
            import_response = await async_client.post(
                "/api/v1/import/opml", files=files
            )
            assert import_response.status_code == status.HTTP_200_OK
            import_data = import_response.json()
            assert import_data["feeds_created"] == 2

            # Verify feeds were created
            feeds_response = await async_client.get("/api/v1/feeds/")
            assert feeds_response.status_code == status.HTTP_200_OK
            feeds_data = feeds_response.json()
            assert len(feeds_data) == 2

            # Export OPML
            export_response = await async_client.get("/api/v1/export/opml")
            assert export_response.status_code == status.HTTP_200_OK
            exported_xml = export_response.text

            # Verify exported content contains imported feeds
            assert "Test Feed 1" in exported_xml
            assert "Test Feed 2" in exported_xml
            assert "https://workflow1.com/feed.xml" in exported_xml
            assert "https://workflow2.com/feed.xml" in exported_xml

    @pytest.mark.asyncio
    async def test_feed_stats_with_read_states_workflow(self, async_client, db_session):
        """Test feed statistics with various read states."""
        # Create feed
        feed = await create_feed(db_session, title="Stats Test Feed")

        # Create multiple items
        items = []
        for i in range(10):
            item = await create_item(db_session, feed_id=feed.id, title=f"Item {i}")
            items.append(item)

        # Mark some items as read
        for i in range(3):
            read_update = {"read": True}
            await async_client.post(
                f"/api/v1/feeds/items/{items[i].id}/read", json=read_update
            )

        # Mark some items as starred (but not read)
        for i in range(3, 6):
            star_update = {"starred": True}
            await async_client.post(
                f"/api/v1/feeds/items/{items[i].id}/read", json=star_update
            )

        # Get feed statistics
        stats_response = await async_client.get(f"/api/v1/feeds/{feed.id}/stats")
        assert stats_response.status_code == status.HTTP_200_OK
        stats_data = stats_response.json()

        assert stats_data["total_items"] == 10
        assert stats_data["unread_items"] == 7  # 10 total - 3 read = 7 unread

    @pytest.mark.asyncio
    async def test_pagination_across_large_dataset(self, async_client, db_session):
        """Test pagination with a large dataset."""
        # Create feed with many items
        feed = await create_feed(db_session, title="Large Dataset Feed")

        # Create 50 items
        for i in range(50):
            await create_item(
                db_session,
                feed_id=feed.id,
                title=f"Item {i:02d}",
                published_at=datetime.utcnow() - timedelta(hours=i),
            )

        # Test pagination
        all_items = []
        skip = 0
        limit = 10

        while True:
            response = await async_client.get(
                f"/api/v1/feeds/{feed.id}/items?skip={skip}&limit={limit}"
            )
            assert response.status_code == status.HTTP_200_OK
            page_data = response.json()

            if not page_data:
                break

            all_items.extend(page_data)
            skip += limit

            if len(page_data) < limit:
                break

        # Should have retrieved all 50 items
        assert len(all_items) == 50

        # Items should be ordered by published_at desc (newest first)
        titles = [item["title"] for item in all_items]
        assert titles[0] == "Item 00"  # Most recent (0 hours ago)
        assert titles[-1] == "Item 49"  # Oldest (49 hours ago)

    @pytest.mark.asyncio
    async def test_feed_validation_workflow(self, async_client):
        """Test feed URL validation workflow."""
        # Test valid feed
        with patch("app.routers.feeds.feedparser.parse") as mock_parse:
            mock_parse.return_value.bozo = False
            mock_parse.return_value.feed = {"title": "Valid Feed"}

            valid_response = await async_client.post(
                "/api/v1/feeds/validate",
                params={"url": "https://valid-feed.com/rss.xml"},
            )
            assert valid_response.status_code == status.HTTP_200_OK
            valid_data = valid_response.json()
            assert valid_data["is_valid"] is True
            assert valid_data["feed_title"] == "Valid Feed"

        # Test invalid feed
        with patch("app.routers.feeds.feedparser.parse") as mock_parse:
            mock_parse.return_value.bozo = True
            mock_parse.return_value.bozo_exception = "Parse error"

            invalid_response = await async_client.post(
                "/api/v1/feeds/validate",
                params={"url": "https://invalid-feed.com/notarss.xml"},
            )
            assert invalid_response.status_code == status.HTTP_200_OK
            invalid_data = invalid_response.json()
            assert invalid_data["is_valid"] is False
            assert "Feed parsing error" in invalid_data["error_message"]

    @pytest.mark.asyncio
    async def test_health_check_workflow(self, async_client):
        """Test health check workflow."""
        # Test liveness (should always work)
        liveness_response = await async_client.get("/api/v1/health/liveness")
        assert liveness_response.status_code == status.HTTP_200_OK
        liveness_data = liveness_response.json()
        assert liveness_data["status"] == "ok"

        # Test readiness with mocked dependencies
        with patch("app.routers.health.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.ping.return_value = True
            mock_get_redis.return_value = mock_redis

            readiness_response = await async_client.get("/api/v1/health/readiness")
            assert readiness_response.status_code == status.HTTP_200_OK
            readiness_data = readiness_response.json()
            assert readiness_data["status"] == "ready"
            assert readiness_data["checks"]["database"] is True
            assert readiness_data["checks"]["redis"] is True

    @pytest.mark.asyncio
    async def test_api_error_handling_workflow(self, async_client):
        """Test API error handling across different scenarios."""
        # Test 404 errors
        fake_id = uuid.uuid4()

        # Non-existent feed
        feed_response = await async_client.get(f"/api/v1/feeds/{fake_id}")
        assert feed_response.status_code == status.HTTP_404_NOT_FOUND

        # Non-existent item
        item_response = await async_client.get(f"/api/v1/feeds/items/{fake_id}")
        assert item_response.status_code == status.HTTP_404_NOT_FOUND

        # Test validation errors
        invalid_feed = {"url": "not-a-url"}
        validation_response = await async_client.post(
            "/api/v1/feeds/", json=invalid_feed
        )
        assert validation_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Test invalid UUIDs
        invalid_uuid_response = await async_client.get("/api/v1/feeds/not-a-uuid")
        assert invalid_uuid_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_concurrent_read_state_updates(self, async_client, db_session):
        """Test concurrent updates to read states."""
        feed = await create_feed(db_session)
        item = await create_item(
            db_session, feed_id=feed.id, title="Concurrent Test Item"
        )

        # Simulate concurrent updates
        import asyncio

        async def mark_read():
            return await async_client.post(
                f"/api/v1/feeds/items/{item.id}/read", json={"read": True}
            )

        async def mark_starred():
            return await async_client.post(
                f"/api/v1/feeds/items/{item.id}/read", json={"starred": True}
            )

        # Execute concurrently
        read_response, star_response = await asyncio.gather(mark_read(), mark_starred())

        assert read_response.status_code == status.HTTP_200_OK
        assert star_response.status_code == status.HTTP_200_OK

        # Verify final state
        detail_response = await async_client.get(f"/api/v1/feeds/items/{item.id}")
        detail_data = detail_response.json()

        # One of the updates should have won (depends on timing)
        # Both updates should have succeeded
        assert detail_data["is_read"] is True or detail_data["starred"] is True

    @pytest.mark.asyncio
    async def test_database_transaction_rollback(self, async_client, db_session):
        """Test database transaction rollback on errors."""
        # This test verifies that failed operations don't leave partial data

        with patch("app.routers.feeds.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            # Create a feed successfully
            feed_data = {"url": "https://transaction-test.com/feed.xml"}
            response = await async_client.post("/api/v1/feeds/", json=feed_data)
            assert response.status_code == status.HTTP_201_CREATED

            # Try to create duplicate (should fail)
            duplicate_response = await async_client.post(
                "/api/v1/feeds/", json=feed_data
            )
            assert duplicate_response.status_code == status.HTTP_400_BAD_REQUEST

            # Verify original feed still exists and is intact
            feeds_response = await async_client.get("/api/v1/feeds/")
            feeds_data = feeds_response.json()
            matching_feeds = [f for f in feeds_data if f["url"] == feed_data["url"]]
            assert len(matching_feeds) == 1  # Only one copy should exist

    @pytest.mark.asyncio
    async def test_api_versioning_consistency(self, async_client):
        """Test API versioning consistency across endpoints."""
        # All endpoints should be under /api/v1/
        endpoints_to_test = [
            "/api/v1/health/liveness",
            "/api/v1/feeds/",
            "/api/v1/categories/",  # CRITICAL: Added to prevent missing categories bug
            "/api/v1/export/opml",
            "/api/v1/sse/events",
        ]

        for endpoint in endpoints_to_test:
            # Just test that endpoints exist (don't test full functionality)
            response = await async_client.get(endpoint)
            # Should not be 404 (endpoint exists)
            assert response.status_code != status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_content_type_consistency(self, async_client, db_session):
        """Test content type consistency across endpoints."""
        feed = await create_feed(db_session)

        # JSON endpoints
        json_endpoints = [
            "/api/v1/",
            "/api/v1/feeds/",
            f"/api/v1/feeds/{feed.id}",
            "/api/v1/health/liveness",
        ]

        for endpoint in json_endpoints:
            response = await async_client.get(endpoint)
            if response.status_code == status.HTTP_200_OK:
                assert "application/json" in response.headers["content-type"]

        # XML endpoint
        xml_response = await async_client.get("/api/v1/export/opml")
        assert xml_response.status_code == status.HTTP_200_OK
        assert "application/xml" in xml_response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_cors_headers_consistency(self, async_client):
        """Test CORS headers consistency across endpoints."""
        origin_header = {"Origin": "http://localhost:3000"}

        endpoints_to_test = ["/api/v1/", "/api/v1/health/liveness", "/api/v1/feeds/"]

        for endpoint in endpoints_to_test:
            response = await async_client.get(endpoint, headers=origin_header)
            if response.status_code == status.HTTP_200_OK:
                # Should have CORS headers
                assert "access-control-allow-origin" in response.headers

    @pytest.mark.asyncio
    async def test_data_consistency_across_endpoints(self, async_client, db_session):
        """Test data consistency when accessed through different endpoints."""
        # Create feed with items
        feed = await create_feed(db_session, title="Consistency Test")
        item = await create_item(db_session, feed_id=feed.id, title="Test Item")

        # Update read state
        await async_client.post(
            f"/api/v1/feeds/items/{item.id}/read", json={"read": True, "starred": True}
        )

        # Check consistency across different endpoints

        # 1. Get item detail
        item_detail_response = await async_client.get(f"/api/v1/feeds/items/{item.id}")
        item_detail = item_detail_response.json()

        # 2. Get item in feed items list
        feed_items_response = await async_client.get(f"/api/v1/feeds/{feed.id}/items")
        feed_items = feed_items_response.json()
        feed_item = next(i for i in feed_items if i["id"] == str(item.id))

        # Data should be consistent
        assert item_detail["is_read"] == feed_item["is_read"]
        assert item_detail["starred"] == feed_item["starred"]
        assert item_detail["title"] == feed_item["title"]
        assert item_detail["url"] == feed_item["url"]

    @pytest.mark.asyncio
    async def test_error_propagation_workflow(self, async_client):
        """Test error propagation through the system."""
        # Test chain of dependent operations
        fake_feed_id = uuid.uuid4()
        fake_item_id = uuid.uuid4()

        # 1. Try to get items for non-existent feed
        items_response = await async_client.get(f"/api/v1/feeds/{fake_feed_id}/items")
        assert items_response.status_code == status.HTTP_200_OK
        assert items_response.json() == []  # Empty list, not error

        # 2. Try to get non-existent item
        item_response = await async_client.get(f"/api/v1/feeds/items/{fake_item_id}")
        assert item_response.status_code == status.HTTP_404_NOT_FOUND

        # 3. Try to update read state for non-existent item
        read_response = await async_client.post(
            f"/api/v1/feeds/items/{fake_item_id}/read", json={"read": True}
        )
        assert read_response.status_code == status.HTTP_404_NOT_FOUND

        # 4. Try to delete non-existent feed
        delete_response = await async_client.delete(f"/api/v1/feeds/{fake_feed_id}")
        assert delete_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_bulk_operations_workflow(self, async_client, db_session):
        """Test bulk operations and their performance."""
        # Create feed
        feed = await create_feed(db_session, title="Bulk Test Feed")

        # Create many items
        items = []
        for i in range(20):
            item = await create_item(
                db_session, feed_id=feed.id, title=f"Bulk Item {i}"
            )
            items.append(item)

        # Bulk mark as read (simulate user marking all as read)
        for item in items[:10]:  # Mark first 10 as read
            await async_client.post(
                f"/api/v1/feeds/items/{item.id}/read", json={"read": True}
            )

        # Verify bulk operation results
        unread_response = await async_client.get(
            f"/api/v1/feeds/{feed.id}/items?unread_only=true"
        )
        unread_data = unread_response.json()
        assert len(unread_data) == 10  # Should have 10 unread items

        # Get stats to verify counts
        stats_response = await async_client.get(f"/api/v1/feeds/{feed.id}/stats")
        stats_data = stats_response.json()
        assert stats_data["total_items"] == 20
        assert stats_data["unread_items"] == 10
