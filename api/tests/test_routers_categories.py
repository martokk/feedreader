import uuid

import pytest
from fastapi import status

from tests.factories import (
    add_feed_to_category,
    create_category,
    create_category_with_feeds,
    create_category_with_items,
    create_feed,
)


class TestCategoriesRouter:
    """Test categories router endpoints."""

    @pytest.mark.asyncio
    async def test_get_categories(self, async_client, db_session):
        """Test getting all categories."""
        # Create test categories
        category1 = await create_category(db_session, name="Tech News", order=1)
        category2 = await create_category(db_session, name="Sports", order=2)

        response = await async_client.get("/api/v1/categories/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

        # Check ordering
        assert data[0]["name"] == "Tech News"
        assert data[1]["name"] == "Sports"

    @pytest.mark.asyncio
    async def test_get_categories_pagination(self, async_client, db_session):
        """Test categories pagination."""
        # Create multiple categories
        for i in range(5):
            await create_category(db_session, name=f"Category {i}", order=i)

        # Test with limit
        response = await async_client.get("/api/v1/categories/?limit=3")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

        # Test with skip and limit
        response = await async_client.get("/api/v1/categories/?skip=2&limit=2")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_get_categories_ordering(self, async_client, db_session):
        """Test categories ordering options."""
        # Create categories with different orders
        await create_category(db_session, name="B Category", order=2)
        await create_category(db_session, name="A Category", order=1)
        await create_category(db_session, name="C Category", order=3)

        # Test order by order field (default)
        response = await async_client.get("/api/v1/categories/?order_by=order")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data[0]["name"] == "A Category"
        assert data[1]["name"] == "B Category"
        assert data[2]["name"] == "C Category"

        # Test order by name
        response = await async_client.get("/api/v1/categories/?order_by=name")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Name ordering is descending, so Z comes first
        names = [cat["name"] for cat in data]
        assert names == sorted(names, reverse=True)

    @pytest.mark.asyncio
    async def test_get_categories_with_stats(self, async_client, db_session):
        """Test getting categories with statistics."""
        # Create category with feeds and items
        category, feeds, items, read_states = await create_category_with_items(
            db_session, name="Test Category", num_feeds=2, items_per_feed=3, num_read=1
        )

        response = await async_client.get("/api/v1/categories/with-stats")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1

        category_data = data[0]
        assert category_data["name"] == "Test Category"
        assert category_data["feed_count"] == 2
        assert category_data["total_items"] == 6  # 2 feeds * 3 items each
        assert category_data["unread_items"] == 4  # 6 total - 2 read (1 per feed)

    @pytest.mark.asyncio
    async def test_get_category_by_id(self, async_client, db_session):
        """Test getting a single category by ID."""
        category = await create_category(
            db_session, name="Test Category", description="A test category"
        )

        response = await async_client.get(f"/api/v1/categories/{category.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(category.id)
        assert data["name"] == "Test Category"
        assert data["description"] == "A test category"

    @pytest.mark.asyncio
    async def test_get_category_not_found(self, async_client, db_session):
        """Test getting a non-existent category."""
        non_existent_id = uuid.uuid4()
        response = await async_client.get(f"/api/v1/categories/{non_existent_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Category not found"

    @pytest.mark.asyncio
    async def test_get_category_with_feeds(self, async_client, db_session):
        """Test getting a category with its feeds."""
        category, feeds = await create_category_with_feeds(
            db_session, name="Test Category", num_feeds=2
        )

        response = await async_client.get(
            f"/api/v1/categories/{category.id}/with-feeds"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Test Category"
        assert len(data["feeds"]) == 2

    @pytest.mark.asyncio
    async def test_get_category_stats(self, async_client, db_session):
        """Test getting category statistics."""
        category, feeds, items, read_states = await create_category_with_items(
            db_session, name="Test Category", num_feeds=2, items_per_feed=3, num_read=1
        )

        response = await async_client.get(f"/api/v1/categories/{category.id}/stats")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["category_id"] == str(category.id)
        assert data["feed_count"] == 2
        assert data["total_items"] == 6
        assert data["unread_items"] == 4
        assert data["last_updated"] is not None

    @pytest.mark.asyncio
    async def test_get_category_feeds(self, async_client, db_session):
        """Test getting feeds in a category."""
        category, feeds = await create_category_with_feeds(
            db_session, name="Test Category", num_feeds=3
        )

        response = await async_client.get(f"/api/v1/categories/{category.id}/feeds")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        feed_ids = {feed["id"] for feed in data}
        expected_ids = {str(feed.id) for feed in feeds}
        assert feed_ids == expected_ids

    @pytest.mark.asyncio
    async def test_get_category_items(self, async_client, db_session):
        """Test getting items from feeds in a category."""
        category, feeds, items, read_states = await create_category_with_items(
            db_session, name="Test Category", num_feeds=2, items_per_feed=3, num_read=1
        )

        response = await async_client.get(f"/api/v1/categories/{category.id}/items")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 6  # 2 feeds * 3 items each

    @pytest.mark.asyncio
    async def test_get_category_items_with_filters(self, async_client, db_session):
        """Test getting category items with filters."""
        category, feeds, items, read_states = await create_category_with_items(
            db_session, name="Test Category", num_feeds=2, items_per_feed=3, num_read=1
        )

        # Test read filter
        response = await async_client.get(
            f"/api/v1/categories/{category.id}/items?read_status=read"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2  # 1 read item per feed

        # Test unread filter
        response = await async_client.get(
            f"/api/v1/categories/{category.id}/items?read_status=unread"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 4  # 2 unread items per feed

        # Test pagination
        response = await async_client.get(
            f"/api/v1/categories/{category.id}/items?limit=3"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_create_category(self, async_client, db_session):
        """Test creating a new category."""
        category_data = {
            "name": "New Category",
            "description": "A new test category",
            "color": "#FF5733",
            "order": 10,
        }

        response = await async_client.post("/api/v1/categories/", json=category_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "New Category"
        assert data["description"] == "A new test category"
        assert data["color"] == "#FF5733"
        assert data["order"] == 10

    @pytest.mark.asyncio
    async def test_create_category_duplicate_name(self, async_client, db_session):
        """Test creating a category with duplicate name."""
        await create_category(db_session, name="Existing Category")

        category_data = {
            "name": "Existing Category",
            "description": "Another category with same name",
        }

        response = await async_client.post("/api/v1/categories/", json=category_data)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_category_validation_errors(self, async_client, db_session):
        """Test category creation validation errors."""
        # Test invalid color
        category_data = {
            "name": "Test Category",
            "color": "invalid-color",
        }

        response = await async_client.post("/api/v1/categories/", json=category_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Test empty name
        category_data = {
            "name": "",
        }

        response = await async_client.post("/api/v1/categories/", json=category_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_update_category(self, async_client, db_session):
        """Test updating a category."""
        category = await create_category(
            db_session, name="Old Name", description="Old description"
        )

        update_data = {
            "name": "New Name",
            "description": "New description",
            "color": "#00FF00",
        }

        response = await async_client.patch(
            f"/api/v1/categories/{category.id}", json=update_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "New Name"
        assert data["description"] == "New description"
        assert data["color"] == "#00FF00"

    @pytest.mark.asyncio
    async def test_update_category_not_found(self, async_client, db_session):
        """Test updating a non-existent category."""
        non_existent_id = uuid.uuid4()
        update_data = {"name": "New Name"}

        response = await async_client.patch(
            f"/api/v1/categories/{non_existent_id}", json=update_data
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_category(self, async_client, db_session):
        """Test deleting a category."""
        category = await create_category(db_session, name="To Delete")

        response = await async_client.delete(f"/api/v1/categories/{category.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify category is deleted
        get_response = await async_client.get(f"/api/v1/categories/{category.id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_category_not_found(self, async_client, db_session):
        """Test deleting a non-existent category."""
        non_existent_id = uuid.uuid4()

        response = await async_client.delete(f"/api/v1/categories/{non_existent_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_add_feeds_to_category_bulk(self, async_client, db_session):
        """Test adding multiple feeds to a category."""
        category = await create_category(db_session, name="Test Category")
        feed1 = await create_feed(db_session, title="Feed 1")
        feed2 = await create_feed(db_session, title="Feed 2")

        bulk_data = {"feed_ids": [str(feed1.id), str(feed2.id)]}

        response = await async_client.post(
            f"/api/v1/categories/{category.id}/feeds", json=bulk_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["added_count"] == 2
        assert data["skipped_count"] == 0

    @pytest.mark.asyncio
    async def test_add_feeds_to_category_duplicates(self, async_client, db_session):
        """Test adding feeds that are already in category."""
        category = await create_category(db_session, name="Test Category")
        feed1 = await create_feed(db_session, title="Feed 1")
        feed2 = await create_feed(db_session, title="Feed 2")

        # Add feed1 to category first
        await add_feed_to_category(db_session, feed1, category)

        # Try to add both feeds
        bulk_data = {"feed_ids": [str(feed1.id), str(feed2.id)]}

        response = await async_client.post(
            f"/api/v1/categories/{category.id}/feeds", json=bulk_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["added_count"] == 1  # Only feed2 was added
        assert data["skipped_count"] == 1  # feed1 was skipped

    @pytest.mark.asyncio
    async def test_add_feeds_to_category_nonexistent_feeds(
        self, async_client, db_session
    ):
        """Test adding non-existent feeds to category."""
        category = await create_category(db_session, name="Test Category")
        nonexistent_id = uuid.uuid4()

        bulk_data = {"feed_ids": [str(nonexistent_id)]}

        response = await async_client.post(
            f"/api/v1/categories/{category.id}/feeds", json=bulk_data
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Feeds not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_remove_feeds_from_category_bulk(self, async_client, db_session):
        """Test removing multiple feeds from a category."""
        category, feeds = await create_category_with_feeds(
            db_session, name="Test Category", num_feeds=3
        )

        # Remove 2 feeds
        bulk_data = {"feed_ids": [str(feeds[0].id), str(feeds[1].id)]}

        response = await async_client.request(
            "DELETE", f"/api/v1/categories/{category.id}/feeds", json=bulk_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["removed_count"] == 2

        # Verify feeds are removed
        get_response = await async_client.get(f"/api/v1/categories/{category.id}/feeds")
        remaining_feeds = get_response.json()
        assert len(remaining_feeds) == 1

    @pytest.mark.asyncio
    async def test_category_not_found_for_bulk_operations(
        self, async_client, db_session
    ):
        """Test bulk operations with non-existent category."""
        nonexistent_id = uuid.uuid4()
        feed = await create_feed(db_session, title="Test Feed")

        bulk_data = {"feed_ids": [str(feed.id)]}

        # Test add
        response = await async_client.post(
            f"/api/v1/categories/{nonexistent_id}/feeds", json=bulk_data
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Test remove
        response = await async_client.request(
            "DELETE", f"/api/v1/categories/{nonexistent_id}/feeds", json=bulk_data
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
