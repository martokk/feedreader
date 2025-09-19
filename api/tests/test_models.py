import uuid
from datetime import datetime, timedelta

import pytest
from app.models import Feed, FetchLog, Item, ReadState
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from tests.factories import (
    FeedFactory,
    FetchLogFactory,
    ItemFactory,
    create_feed,
    create_fetch_log,
    create_item,
    create_read_state,
)


class TestFeedModel:
    """Test Feed model."""

    @pytest.mark.asyncio
    async def test_create_feed(self, db_session):
        """Test creating a feed."""
        feed_data = FeedFactory.build()
        feed = Feed(**feed_data.__dict__)

        db_session.add(feed)
        await db_session.commit()
        await db_session.refresh(feed)

        assert feed.id is not None
        assert feed.url == feed_data.url
        assert feed.title == feed_data.title
        assert feed.created_at is not None
        assert feed.updated_at is not None

    @pytest.mark.asyncio
    async def test_feed_unique_url_constraint(self, db_session):
        """Test that feed URLs must be unique."""
        url = "https://example.com/feed.xml"

        # Create first feed
        feed1 = await create_feed(db_session, url=url)
        assert feed1.id is not None

        # Try to create second feed with same URL
        feed2 = Feed(
            url=url,
            title="Another Feed",
            interval_seconds=1800,
            per_host_key="example.com",
            next_run_at=datetime.utcnow() + timedelta(minutes=15),
        )

        db_session.add(feed2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_feed_relationships(self, db_session):
        """Test feed relationships with items and fetch logs."""
        feed = await create_feed(db_session)

        # Create items for the feed
        item1 = await create_item(db_session, feed_id=feed.id)
        item2 = await create_item(db_session, feed_id=feed.id)

        # Create fetch logs for the feed
        fetch_log1 = await create_fetch_log(db_session, feed_id=feed.id)
        fetch_log2 = await create_fetch_log(db_session, feed_id=feed.id)

        # Refresh feed to get relationships
        await db_session.refresh(feed, ["items", "fetch_logs"])

        assert len(feed.items) == 2
        assert len(feed.fetch_logs) == 2
        assert item1 in feed.items
        assert item2 in feed.items
        assert fetch_log1 in feed.fetch_logs
        assert fetch_log2 in feed.fetch_logs

    @pytest.mark.asyncio
    async def test_feed_cascade_delete(self, db_session):
        """Test that deleting a feed cascades to items and fetch logs."""
        feed = await create_feed(db_session)

        # Create related records
        item = await create_item(db_session, feed_id=feed.id)
        fetch_log = await create_fetch_log(db_session, feed_id=feed.id)

        # Delete the feed
        await db_session.delete(feed)
        await db_session.commit()

        # Check that related records are deleted
        stmt = select(Item).where(Item.id == item.id)
        result = await db_session.execute(stmt)
        assert result.scalar_one_or_none() is None

        stmt = select(FetchLog).where(FetchLog.id == fetch_log.id)
        result = await db_session.execute(stmt)
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_feed_indexes(self, db_session):
        """Test that feed indexes work correctly."""
        # Create feeds with different next_run_at times
        now = datetime.utcnow()
        feed1 = await create_feed(db_session, next_run_at=now + timedelta(minutes=5))
        feed2 = await create_feed(db_session, next_run_at=now + timedelta(minutes=10))
        feed3 = await create_feed(db_session, next_run_at=now + timedelta(minutes=15))

        # Query by next_run_at (should use index)
        stmt = (
            select(Feed)
            .where(Feed.next_run_at <= now + timedelta(minutes=7))
            .order_by(Feed.next_run_at)
        )
        result = await db_session.execute(stmt)
        feeds = result.scalars().all()

        assert len(feeds) == 1
        assert feeds[0].id == feed1.id


class TestItemModel:
    """Test Item model."""

    @pytest.mark.asyncio
    async def test_create_item(self, db_session):
        """Test creating an item."""
        feed = await create_feed(db_session)
        item_data = ItemFactory.build(feed_id=feed.id)
        item = Item(**item_data.__dict__)

        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        assert item.id is not None
        assert item.feed_id == feed.id
        assert item.guid == item_data.guid
        assert item.title == item_data.title
        assert item.created_at is not None
        assert item.updated_at is not None

    @pytest.mark.asyncio
    async def test_item_unique_feed_guid_constraint(self, db_session):
        """Test that items must have unique guid per feed."""
        feed = await create_feed(db_session)
        guid = "test-guid-123"

        # Create first item
        item1 = await create_item(db_session, feed_id=feed.id, guid=guid)
        assert item1.id is not None

        # Try to create second item with same feed_id and guid
        item2 = Item(
            feed_id=feed.id,
            guid=guid,
            title="Another Item",
            fetched_at=datetime.utcnow(),
            hash="different-hash",
        )

        db_session.add(item2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_item_same_guid_different_feeds(self, db_session):
        """Test that same guid can exist in different feeds."""
        feed1 = await create_feed(db_session)
        feed2 = await create_feed(db_session)
        guid = "test-guid-123"

        # Create items with same guid in different feeds
        item1 = await create_item(db_session, feed_id=feed1.id, guid=guid)
        item2 = await create_item(db_session, feed_id=feed2.id, guid=guid)

        assert item1.id != item2.id
        assert item1.feed_id != item2.feed_id
        assert item1.guid == item2.guid

    @pytest.mark.asyncio
    async def test_item_feed_relationship(self, db_session):
        """Test item-feed relationship."""
        feed = await create_feed(db_session)
        item = await create_item(db_session, feed_id=feed.id)

        # Load relationship
        await db_session.refresh(item, ["feed"])

        assert item.feed is not None
        assert item.feed.id == feed.id

    @pytest.mark.asyncio
    async def test_item_read_state_relationship(self, db_session):
        """Test item-read_state relationship."""
        feed = await create_feed(db_session)
        item = await create_item(db_session, feed_id=feed.id)
        read_state = await create_read_state(db_session, item_id=item.id)

        # Load relationship
        await db_session.refresh(item, ["read_state"])

        assert item.read_state is not None
        assert item.read_state.item_id == item.id

    @pytest.mark.asyncio
    async def test_item_indexes(self, db_session):
        """Test item indexes."""
        feed = await create_feed(db_session)
        now = datetime.utcnow()

        # Create items with different published_at times
        item1 = await create_item(
            db_session, feed_id=feed.id, published_at=now - timedelta(hours=2)
        )
        item2 = await create_item(
            db_session, feed_id=feed.id, published_at=now - timedelta(hours=1)
        )
        item3 = await create_item(db_session, feed_id=feed.id, published_at=now)

        # Query by published_at (should use index)
        stmt = (
            select(Item)
            .where(Item.published_at >= now - timedelta(hours=1.5))
            .order_by(Item.published_at.desc())
        )
        result = await db_session.execute(stmt)
        items = result.scalars().all()

        assert len(items) == 2
        assert items[0].id == item3.id
        assert items[1].id == item2.id


class TestReadStateModel:
    """Test ReadState model."""

    @pytest.mark.asyncio
    async def test_create_read_state(self, db_session):
        """Test creating a read state."""
        feed = await create_feed(db_session)
        item = await create_item(db_session, feed_id=feed.id)

        read_state = ReadState(item_id=item.id, read_at=datetime.utcnow(), starred=True)

        db_session.add(read_state)
        await db_session.commit()
        await db_session.refresh(read_state)

        assert read_state.item_id == item.id
        assert read_state.read_at is not None
        assert read_state.starred is True

    @pytest.mark.asyncio
    async def test_read_state_unread_default(self, db_session):
        """Test that read_at defaults to None (unread)."""
        feed = await create_feed(db_session)
        item = await create_item(db_session, feed_id=feed.id)

        read_state = ReadState(item_id=item.id)
        db_session.add(read_state)
        await db_session.commit()
        await db_session.refresh(read_state)

        assert read_state.read_at is None
        assert read_state.starred is False

    @pytest.mark.asyncio
    async def test_read_state_item_relationship(self, db_session):
        """Test read_state-item relationship."""
        feed = await create_feed(db_session)
        item = await create_item(db_session, feed_id=feed.id)
        read_state = await create_read_state(db_session, item_id=item.id)

        # Load relationship
        await db_session.refresh(read_state, ["item"])

        assert read_state.item is not None
        assert read_state.item.id == item.id

    @pytest.mark.asyncio
    async def test_read_state_cascade_delete_with_item(self, db_session):
        """Test that deleting an item deletes its read state."""
        feed = await create_feed(db_session)
        item = await create_item(db_session, feed_id=feed.id)
        read_state = await create_read_state(db_session, item_id=item.id)

        # Delete the item
        await db_session.delete(item)
        await db_session.commit()

        # Check that read state is deleted
        stmt = select(ReadState).where(ReadState.item_id == item.id)
        result = await db_session.execute(stmt)
        assert result.scalar_one_or_none() is None


class TestFetchLogModel:
    """Test FetchLog model."""

    @pytest.mark.asyncio
    async def test_create_fetch_log(self, db_session):
        """Test creating a fetch log."""
        feed = await create_feed(db_session)
        fetch_log_data = FetchLogFactory.build(feed_id=feed.id)
        fetch_log = FetchLog(**fetch_log_data.__dict__)

        db_session.add(fetch_log)
        await db_session.commit()
        await db_session.refresh(fetch_log)

        assert fetch_log.id is not None
        assert fetch_log.feed_id == feed.id
        assert fetch_log.status_code == fetch_log_data.status_code
        assert fetch_log.duration_ms == fetch_log_data.duration_ms
        assert fetch_log.fetched_at is not None

    @pytest.mark.asyncio
    async def test_fetch_log_with_error(self, db_session):
        """Test creating a fetch log with error."""
        feed = await create_feed(db_session)
        error_message = "Connection timeout"

        fetch_log = await create_fetch_log(
            db_session, feed_id=feed.id, status_code=408, error=error_message
        )

        assert fetch_log.error == error_message
        assert fetch_log.status_code == 408

    @pytest.mark.asyncio
    async def test_fetch_log_feed_relationship(self, db_session):
        """Test fetch_log-feed relationship."""
        feed = await create_feed(db_session)
        fetch_log = await create_fetch_log(db_session, feed_id=feed.id)

        # Load relationship
        await db_session.refresh(fetch_log, ["feed"])

        assert fetch_log.feed is not None
        assert fetch_log.feed.id == feed.id


class TestModelMixins:
    """Test base model mixins."""

    @pytest.mark.asyncio
    async def test_timestamp_mixin(self, db_session):
        """Test that timestamp mixin works correctly."""
        feed = await create_feed(db_session)

        original_created = feed.created_at
        original_updated = feed.updated_at

        # Update the feed
        feed.title = "Updated Title"
        await db_session.commit()
        await db_session.refresh(feed)

        assert feed.created_at == original_created  # Should not change
        assert feed.updated_at > original_updated  # Should be updated

    @pytest.mark.asyncio
    async def test_uuid_mixin(self, db_session):
        """Test that UUID mixin generates valid UUIDs."""
        feed = await create_feed(db_session)
        item = await create_item(db_session, feed_id=feed.id)
        fetch_log = await create_fetch_log(db_session, feed_id=feed.id)

        # Check that all IDs are valid UUIDs
        assert isinstance(feed.id, uuid.UUID)
        assert isinstance(item.id, uuid.UUID)
        assert isinstance(fetch_log.id, uuid.UUID)

        # Check that IDs are unique
        assert feed.id != item.id
        assert feed.id != fetch_log.id
        assert item.id != fetch_log.id
