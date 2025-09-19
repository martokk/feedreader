import uuid

import pytest
from fastapi import status

from tests.factories import (
    add_feed_to_category,
    create_category,
    create_feed,
)


class TestFeedsCategoriesRouter:
    """Test feed category management endpoints."""

    @pytest.mark.asyncio
    async def test_get_feed_categories(self, async_client, db_session):
        """Test getting all categories for a feed."""
        feed = await create_feed(db_session, title="Test Feed")
        category1 = await create_category(db_session, name="Tech", order=1)
        category2 = await create_category(db_session, name="News", order=2)

        # Add feed to categories
        await add_feed_to_category(db_session, feed, category1)
        await add_feed_to_category(db_session, feed, category2)

        response = await async_client.get(f"/api/v1/feeds/{feed.id}/categories")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

        # Check ordering by order field
        assert data[0]["name"] == "Tech"
        assert data[1]["name"] == "News"

    @pytest.mark.asyncio
    async def test_get_feed_categories_empty(self, async_client, db_session):
        """Test getting categories for a feed with no categories."""
        feed = await create_feed(db_session, title="Test Feed")

        response = await async_client.get(f"/api/v1/feeds/{feed.id}/categories")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_get_feed_categories_not_found(self, async_client, db_session):
        """Test getting categories for a non-existent feed."""
        non_existent_id = uuid.uuid4()

        response = await async_client.get(f"/api/v1/feeds/{non_existent_id}/categories")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Feed not found"

    @pytest.mark.asyncio
    async def test_add_feed_to_category(self, async_client, db_session):
        """Test adding a feed to a category."""
        feed = await create_feed(db_session, title="Test Feed")
        category = await create_category(db_session, name="Tech")

        response = await async_client.post(
            f"/api/v1/feeds/{feed.id}/categories?category_id={category.id}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "Successfully added feed to category" in data["message"]
        assert data["category_name"] == "Tech"
        assert data["feed_title"] == "Test Feed"

    @pytest.mark.asyncio
    async def test_add_feed_to_category_duplicate(self, async_client, db_session):
        """Test adding a feed to a category it's already in."""
        feed = await create_feed(db_session, title="Test Feed")
        category = await create_category(db_session, name="Tech")

        # Add feed to category first
        await add_feed_to_category(db_session, feed, category)

        response = await async_client.post(
            f"/api/v1/feeds/{feed.id}/categories?category_id={category.id}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "already in this category" in data["message"]

    @pytest.mark.asyncio
    async def test_add_feed_to_category_feed_not_found(self, async_client, db_session):
        """Test adding a non-existent feed to a category."""
        non_existent_feed_id = uuid.uuid4()
        category = await create_category(db_session, name="Tech")

        response = await async_client.post(
            f"/api/v1/feeds/{non_existent_feed_id}/categories?category_id={category.id}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Feed not found"

    @pytest.mark.asyncio
    async def test_add_feed_to_category_category_not_found(
        self, async_client, db_session
    ):
        """Test adding a feed to a non-existent category."""
        feed = await create_feed(db_session, title="Test Feed")
        non_existent_category_id = uuid.uuid4()

        response = await async_client.post(
            f"/api/v1/feeds/{feed.id}/categories?category_id={non_existent_category_id}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Category not found"

    @pytest.mark.asyncio
    async def test_remove_feed_from_category(self, async_client, db_session):
        """Test removing a feed from a category."""
        feed = await create_feed(db_session, title="Test Feed")
        category = await create_category(db_session, name="Tech")

        # Add feed to category first
        await add_feed_to_category(db_session, feed, category)

        response = await async_client.delete(
            f"/api/v1/feeds/{feed.id}/categories/{category.id}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "Successfully removed feed from category" in data["message"]
        assert data["category_name"] == "Tech"
        assert data["feed_title"] == "Test Feed"

    @pytest.mark.asyncio
    async def test_remove_feed_from_category_not_in_category(
        self, async_client, db_session
    ):
        """Test removing a feed from a category it's not in."""
        feed = await create_feed(db_session, title="Test Feed")
        category = await create_category(db_session, name="Tech")

        response = await async_client.delete(
            f"/api/v1/feeds/{feed.id}/categories/{category.id}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "was not in this category" in data["message"]

    @pytest.mark.asyncio
    async def test_remove_feed_from_category_feed_not_found(
        self, async_client, db_session
    ):
        """Test removing a non-existent feed from a category."""
        non_existent_feed_id = uuid.uuid4()
        category = await create_category(db_session, name="Tech")

        response = await async_client.delete(
            f"/api/v1/feeds/{non_existent_feed_id}/categories/{category.id}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Feed not found"

    @pytest.mark.asyncio
    async def test_remove_feed_from_category_category_not_found(
        self, async_client, db_session
    ):
        """Test removing a feed from a non-existent category."""
        feed = await create_feed(db_session, title="Test Feed")
        non_existent_category_id = uuid.uuid4()

        response = await async_client.delete(
            f"/api/v1/feeds/{feed.id}/categories/{non_existent_category_id}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Category not found"

    @pytest.mark.asyncio
    async def test_feed_category_workflow(self, async_client, db_session):
        """Test complete workflow of managing feed categories."""
        feed = await create_feed(db_session, title="Test Feed")
        category1 = await create_category(db_session, name="Tech", order=1)
        category2 = await create_category(db_session, name="News", order=2)

        # Initially no categories
        response = await async_client.get(f"/api/v1/feeds/{feed.id}/categories")
        assert len(response.json()) == 0

        # Add to first category
        response = await async_client.post(
            f"/api/v1/feeds/{feed.id}/categories?category_id={category1.id}"
        )
        assert response.status_code == status.HTTP_200_OK

        # Check categories
        response = await async_client.get(f"/api/v1/feeds/{feed.id}/categories")
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Tech"

        # Add to second category
        response = await async_client.post(
            f"/api/v1/feeds/{feed.id}/categories?category_id={category2.id}"
        )
        assert response.status_code == status.HTTP_200_OK

        # Check categories
        response = await async_client.get(f"/api/v1/feeds/{feed.id}/categories")
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "Tech"  # order=1
        assert data[1]["name"] == "News"  # order=2

        # Remove from first category
        response = await async_client.delete(
            f"/api/v1/feeds/{feed.id}/categories/{category1.id}"
        )
        assert response.status_code == status.HTTP_200_OK

        # Check categories
        response = await async_client.get(f"/api/v1/feeds/{feed.id}/categories")
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "News"
