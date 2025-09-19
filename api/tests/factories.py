import uuid
from datetime import datetime, timedelta

import factory
from app.models import Category, Feed, FetchLog, Item, ReadState
from app.models.category import category_feed
from factory import Faker, LazyAttribute
from sqlalchemy.ext.asyncio import AsyncSession


class FeedFactory(factory.Factory):
    """Factory for creating Feed instances."""

    class Meta:
        model = Feed

    id = factory.LazyFunction(uuid.uuid4)
    url = Faker("url")
    title = Faker("sentence", nb_words=4)
    etag = Faker("sha256")
    last_modified = factory.LazyFunction(lambda: datetime.utcnow() - timedelta(hours=1))
    last_fetch_at = factory.LazyFunction(
        lambda: datetime.utcnow() - timedelta(minutes=30)
    )
    last_status = 200
    next_run_at = factory.LazyFunction(
        lambda: datetime.utcnow() + timedelta(minutes=15)
    )
    interval_seconds = 900
    per_host_key = LazyAttribute(lambda obj: obj.url.split("//")[1].split("/")[0])
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class ItemFactory(factory.Factory):
    """Factory for creating Item instances."""

    class Meta:
        model = Item

    id = factory.LazyFunction(uuid.uuid4)
    feed_id = factory.LazyFunction(uuid.uuid4)
    guid = Faker("uuid4")
    title = Faker("sentence", nb_words=6)
    url = Faker("url")
    content_html = Faker("text", max_nb_chars=1000)
    content_text = LazyAttribute(
        lambda obj: obj.content_html.replace("<p>", "").replace("</p>", "")
    )
    published_at = factory.LazyFunction(lambda: datetime.utcnow() - timedelta(hours=2))
    fetched_at = factory.LazyFunction(lambda: datetime.utcnow() - timedelta(minutes=30))
    hash = Faker("sha256")
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class ReadStateFactory(factory.Factory):
    """Factory for creating ReadState instances."""

    class Meta:
        model = ReadState

    item_id = factory.LazyFunction(uuid.uuid4)
    read_at = None  # Default to unread
    starred = False


class FetchLogFactory(factory.Factory):
    """Factory for creating FetchLog instances."""

    class Meta:
        model = FetchLog

    id = factory.LazyFunction(uuid.uuid4)
    feed_id = factory.LazyFunction(uuid.uuid4)
    status_code = 200
    duration_ms = Faker("random_int", min=100, max=5000)
    bytes = Faker("random_int", min=1000, max=100000)
    error = None
    fetched_at = factory.LazyFunction(datetime.utcnow)


# Async factory helpers
async def create_feed(session: AsyncSession, **kwargs) -> Feed:
    """Create a feed in the database."""
    feed_data = FeedFactory.build(**kwargs)
    # Convert factory object to dict, excluding SQLAlchemy internal attributes
    feed_dict = {k: v for k, v in feed_data.__dict__.items() if not k.startswith("_")}
    feed = Feed(**feed_dict)
    session.add(feed)
    await session.commit()
    await session.refresh(feed)
    return feed


async def create_item(
    session: AsyncSession, feed_id: uuid.UUID = None, **kwargs
) -> Item:
    """Create an item in the database."""
    if feed_id:
        kwargs["feed_id"] = feed_id
    item_data = ItemFactory.build(**kwargs)
    # Convert factory object to dict, excluding SQLAlchemy internal attributes
    item_dict = {k: v for k, v in item_data.__dict__.items() if not k.startswith("_")}
    item = Item(**item_dict)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def create_read_state(
    session: AsyncSession, item_id: uuid.UUID, **kwargs
) -> ReadState:
    """Create a read state in the database."""
    kwargs["item_id"] = item_id
    read_state_data = ReadStateFactory.build(**kwargs)
    # Convert factory object to dict, excluding SQLAlchemy internal attributes
    read_state_dict = {
        k: v for k, v in read_state_data.__dict__.items() if not k.startswith("_")
    }
    read_state = ReadState(**read_state_dict)
    session.add(read_state)
    await session.commit()
    await session.refresh(read_state)
    return read_state


async def create_fetch_log(
    session: AsyncSession, feed_id: uuid.UUID = None, **kwargs
) -> FetchLog:
    """Create a fetch log in the database."""
    if feed_id:
        kwargs["feed_id"] = feed_id
    fetch_log_data = FetchLogFactory.build(**kwargs)
    # Convert factory object to dict, excluding SQLAlchemy internal attributes
    fetch_log_dict = {
        k: v for k, v in fetch_log_data.__dict__.items() if not k.startswith("_")
    }
    fetch_log = FetchLog(**fetch_log_dict)
    session.add(fetch_log)
    await session.commit()
    await session.refresh(fetch_log)
    return fetch_log


# Convenience functions for creating related data
async def create_feed_with_items(
    session: AsyncSession, num_items: int = 3, num_read: int = 1, **feed_kwargs
) -> tuple[Feed, list[Item], list[ReadState]]:
    """Create a feed with items and some read states."""
    feed = await create_feed(session, **feed_kwargs)

    items = []
    read_states = []

    for i in range(num_items):
        item = await create_item(session, feed_id=feed.id)
        items.append(item)

        # Mark some items as read
        if i < num_read:
            read_state = await create_read_state(
                session, item_id=item.id, read_at=datetime.utcnow()
            )
            read_states.append(read_state)

    return feed, items, read_states


class CategoryFactory(factory.Factory):
    """Factory for creating Category instances."""

    class Meta:
        model = Category

    id = factory.LazyFunction(uuid.uuid4)
    name = Faker("word", unique=True)
    description = Faker("sentence", nb_words=8)
    color = Faker("color")
    order = Faker("random_int", min=0, max=100)
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


# Async category factory helpers
async def create_category(session: AsyncSession, **kwargs) -> Category:
    """Create a category in the database."""
    category_data = CategoryFactory.build(**kwargs)
    # Convert factory object to dict, excluding SQLAlchemy internal attributes
    category_dict = {
        k: v for k, v in category_data.__dict__.items() if not k.startswith("_")
    }
    category = Category(**category_dict)
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


async def create_category_with_feeds(
    session: AsyncSession, num_feeds: int = 2, **category_kwargs
) -> tuple[Category, list[Feed]]:
    """Create a category with feeds."""
    category = await create_category(session, **category_kwargs)

    feeds = []
    for i in range(num_feeds):
        feed = await create_feed(session, title=f"Feed {i} for {category.name}")
        feeds.append(feed)

        # Add feed to category
        insert_stmt = category_feed.insert().values(
            category_id=category.id,
            feed_id=feed.id,
            created_at=datetime.utcnow().isoformat(),
        )
        await session.execute(insert_stmt)

    await session.commit()
    return category, feeds


async def create_category_with_items(
    session: AsyncSession,
    num_feeds: int = 2,
    items_per_feed: int = 3,
    num_read: int = 1,
    **category_kwargs,
) -> tuple[Category, list[Feed], list[Item], list[ReadState]]:
    """Create a category with feeds and items."""
    category, feeds = await create_category_with_feeds(
        session, num_feeds, **category_kwargs
    )

    all_items = []
    all_read_states = []

    for feed in feeds:
        for i in range(items_per_feed):
            item = await create_item(session, feed_id=feed.id)
            all_items.append(item)

            # Mark some items as read
            if i < num_read:
                read_state = await create_read_state(
                    session, item_id=item.id, read_at=datetime.utcnow()
                )
                all_read_states.append(read_state)

    return category, feeds, all_items, all_read_states


async def add_feed_to_category(
    session: AsyncSession, feed: Feed, category: Category
) -> None:
    """Add a feed to a category."""
    insert_stmt = category_feed.insert().values(
        category_id=category.id,
        feed_id=feed.id,
        created_at=datetime.utcnow().isoformat(),
    )
    await session.execute(insert_stmt)
    await session.commit()
