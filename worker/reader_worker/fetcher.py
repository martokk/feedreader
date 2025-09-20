import asyncio
import hashlib
import time
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import feedparser
import httpx
import redis.asyncio as redis
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from .config import settings
from .database import get_db_session
from .models import Feed, FetchLog, Item


class ContentExtractor:
    """Content extraction using trafilatura or readability."""

    def __init__(self, engine: str = "trafilatura"):
        self.engine = engine

    def extract_content(
        self, html: str, url: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract content from HTML. Returns (html_content, text_content)."""
        if self.engine == "trafilatura":
            return self._extract_trafilatura(html, url)
        elif self.engine == "readability":
            return self._extract_readability(html)
        else:
            return None, None

    def _extract_trafilatura(
        self, html: str, url: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract using trafilatura."""
        try:
            import trafilatura

            # Extract text content
            text_content = trafilatura.extract(html, url=url)

            # Extract HTML content with formatting
            html_content = trafilatura.extract(
                html,
                url=url,
                output_format="xml",
                include_formatting=True,
                include_links=True,
            )

            return html_content, text_content
        except ImportError:
            return None, None
        except Exception:
            return None, None

    def _extract_readability(self, html: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract using readability-lxml."""
        try:
            from readability import Document

            doc = Document(html)
            html_content = doc.summary()
            text_content = doc.short_title()  # Basic text extraction

            return html_content, text_content
        except ImportError:
            return None, None
        except Exception:
            return None, None


class FeedFetcher:
    """RSS feed fetcher with HTTP caching and content extraction."""

    def __init__(self):
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.fetch_timeout_seconds),
            limits=httpx.Limits(
                max_connections=settings.fetch_concurrency, max_keepalive_connections=20
            ),
            headers={"User-Agent": "RSS-Reader/1.0 (Self-hosted RSS reader)"},
        )
        self.content_extractor = ContentExtractor(settings.extraction_engine)
        self.redis_client = None

        # Per-host semaphores for rate limiting
        self.host_semaphores: Dict[str, asyncio.Semaphore] = {}

    async def get_redis(self) -> redis.Redis:
        """Get Redis client."""
        if self.redis_client is None:
            self.redis_client = redis.from_url(settings.redis_url)
        return self.redis_client

    def get_host_semaphore(self, host: str) -> asyncio.Semaphore:
        """Get or create semaphore for host rate limiting."""
        if host not in self.host_semaphores:
            self.host_semaphores[host] = asyncio.Semaphore(
                settings.per_host_concurrency
            )
        return self.host_semaphores[host]

    async def fetch_feed(self, feed: Feed) -> Dict:
        """Fetch and process a single feed."""
        start_time = time.time()
        parsed_url = urlparse(feed.url)
        host = parsed_url.netloc

        # Get per-host semaphore
        semaphore = self.get_host_semaphore(host)

        async with semaphore:
            try:
                # Build request headers with caching
                headers = {}
                if feed.etag:
                    headers["If-None-Match"] = feed.etag
                if feed.last_modified:
                    headers["If-Modified-Since"] = feed.last_modified.strftime(
                        "%a, %d %b %Y %H:%M:%S GMT"
                    )

                # Fetch feed
                response = await self.http_client.get(feed.url, headers=headers)
                duration_ms = int((time.time() - start_time) * 1000)

                # Handle 304 Not Modified
                if response.status_code == 304:
                    await self._log_fetch(feed.id, 304, duration_ms, 0, None)
                    await self._update_feed_status(feed, 304, None, None)
                    return {
                        "status": "not_modified",
                        "feed_id": str(feed.id),
                        "new_items": 0,
                    }

                # Handle other HTTP errors
                if response.status_code != 200:
                    error_msg = f"HTTP {response.status_code}"
                    await self._log_fetch(
                        feed.id, response.status_code, duration_ms, 0, error_msg
                    )
                    await self._update_feed_status(
                        feed, response.status_code, None, None
                    )
                    return {
                        "status": "error",
                        "feed_id": str(feed.id),
                        "error": error_msg,
                    }

                # Parse feed
                content = response.content
                parsed_feed = feedparser.parse(content)

                if parsed_feed.bozo and not parsed_feed.entries:
                    error_msg = f"Feed parse error: {getattr(parsed_feed, 'bozo_exception', 'Unknown error')}"
                    await self._log_fetch(
                        feed.id, 200, duration_ms, len(content), error_msg
                    )
                    return {
                        "status": "error",
                        "feed_id": str(feed.id),
                        "error": error_msg,
                    }

                # Process entries
                new_items = await self._process_entries(feed, parsed_feed.entries)

                # Update feed metadata
                etag = response.headers.get("etag")
                last_modified_str = response.headers.get("last-modified")
                last_modified = None
                if last_modified_str:
                    try:
                        last_modified = parsedate_to_datetime(last_modified_str)
                    except Exception:
                        pass

                # Update feed title if not set
                feed_title = feed.title
                if (
                    not feed_title
                    and hasattr(parsed_feed, "feed")
                    and hasattr(parsed_feed.feed, "title")
                ):
                    feed_title = parsed_feed.feed.title[:512]  # Truncate to fit DB

                await self._update_feed_status(
                    feed, 200, etag, last_modified, feed_title
                )
                await self._log_fetch(feed.id, 200, duration_ms, len(content), None)

                # Publish notification if new items
                if new_items > 0:
                    await self._publish_new_items_event(feed.id, new_items)

                return {
                    "status": "success",
                    "feed_id": str(feed.id),
                    "new_items": new_items,
                }

            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                error_msg = str(e)
                await self._log_fetch(feed.id, 0, duration_ms, 0, error_msg)
                await self._update_feed_status(feed, 0, None, None)
                return {"status": "error", "feed_id": str(feed.id), "error": error_msg}

    async def _process_entries(self, feed: Feed, entries: List) -> int:
        """Process feed entries and create items."""
        if not entries:
            return 0

        new_items_count = 0
        items_to_insert = []

        async with get_db_session() as db:
            for entry in entries:
                # Generate GUID
                guid = self._get_entry_guid(entry)
                if not guid:
                    continue

                # Check if item already exists
                stmt = select(Item).where(Item.feed_id == feed.id, Item.guid == guid)
                result = await db.execute(stmt)
                existing_item = result.scalar_one_or_none()

                if existing_item:
                    continue

                # Extract item data
                title = (
                    getattr(entry, "title", "")[:1024]
                    if hasattr(entry, "title")
                    else None
                )
                url = (
                    getattr(entry, "link", "")[:2048]
                    if hasattr(entry, "link")
                    else None
                )

                # Get published date
                published_at = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published_at = datetime(
                            *entry.published_parsed[:6], tzinfo=timezone.utc
                        )
                    except (ValueError, TypeError):
                        pass
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    try:
                        published_at = datetime(
                            *entry.updated_parsed[:6], tzinfo=timezone.utc
                        )
                    except (ValueError, TypeError):
                        pass

                # Get content
                content_html = None
                content_text = None

                # Try to get content from entry
                if hasattr(entry, "content") and entry.content:
                    content_html = entry.content[0].value
                elif hasattr(entry, "summary"):
                    content_html = entry.summary

                # Extract image URL from entry
                image_url = None
                
                # Try media:thumbnail first (common in RSS 2.0)
                if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                    image_url = entry.media_thumbnail[0].get("url")
                # Try enclosure for media files
                elif hasattr(entry, "enclosures") and entry.enclosures:
                    for enclosure in entry.enclosures:
                        if enclosure.get("type", "").startswith("image/"):
                            image_url = enclosure.get("href")
                            break
                # Try links for images
                elif hasattr(entry, "links") and entry.links:
                    for link in entry.links:
                        if link.get("type", "").startswith("image/"):
                            image_url = link.get("href")
                            break
                # Try media_content
                elif hasattr(entry, "media_content") and entry.media_content:
                    for media in entry.media_content:
                        if media.get("type", "").startswith("image/"):
                            image_url = media.get("url")
                            break
                
                # Fallback: look for images in content
                if not image_url and content_html:
                    import re
                    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content_html, re.IGNORECASE)
                    if img_match:
                        image_url = img_match.group(1)
                
                # Ensure image URL is valid and truncate if too long
                if image_url and len(image_url) > 2048:
                    image_url = image_url[:2048]

                # Extract full content if URL available
                if url and settings.extraction_engine != "none":
                    try:
                        article_response = await self.http_client.get(url)
                        if article_response.status_code == 200:
                            extracted_html, extracted_text = (
                                self.content_extractor.extract_content(
                                    article_response.text, url
                                )
                            )
                            if extracted_html:
                                content_html = extracted_html
                            if extracted_text:
                                content_text = extracted_text
                    except Exception:
                        # Fallback to entry content
                        pass

                # Create content hash
                content_for_hash = content_html or content_text or title or url or ""
                content_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()

                # Create item
                now = datetime.utcnow()
                item_data = {
                    "id": uuid.uuid4(),
                    "feed_id": feed.id,
                    "guid": guid,
                    "title": title,
                    "url": url,
                    "image_url": image_url,
                    "content_html": content_html,
                    "content_text": content_text,
                    "published_at": published_at,
                    "fetched_at": now,
                    "hash": content_hash,
                    "created_at": now,
                    "updated_at": now,
                }

                items_to_insert.append(item_data)
                new_items_count += 1

            # Bulk insert new items
            if items_to_insert:
                stmt = insert(Item).values(items_to_insert)
                await db.execute(stmt)
                await db.commit()

        return new_items_count

    def _get_entry_guid(self, entry) -> Optional[str]:
        """Get unique identifier for entry."""
        if hasattr(entry, "id") and entry.id:
            return entry.id[:512]
        elif hasattr(entry, "link") and entry.link:
            return entry.link[:512]
        elif hasattr(entry, "title") and entry.title:
            # Use title + published date as fallback
            guid_base = entry.title
            if hasattr(entry, "published"):
                guid_base += entry.published
            return hashlib.sha256(guid_base.encode()).hexdigest()[:512]
        return None

    async def _update_feed_status(
        self,
        feed: Feed,
        status_code: int,
        etag: Optional[str],
        last_modified: Optional[datetime],
        title: Optional[str] = None,
    ):
        """Update feed status in database."""
        async with get_db_session() as db:
            update_data = {
                "last_fetch_at": datetime.utcnow(),
                "last_status": status_code,
                "updated_at": datetime.utcnow(),
            }

            if etag is not None:
                update_data["etag"] = etag
            if last_modified is not None:
                update_data["last_modified"] = last_modified
            if title is not None:
                update_data["title"] = title

            stmt = update(Feed).where(Feed.id == feed.id).values(update_data)
            await db.execute(stmt)
            await db.commit()

    async def _log_fetch(
        self,
        feed_id: uuid.UUID,
        status_code: int,
        duration_ms: int,
        bytes_count: int,
        error: Optional[str],
    ):
        """Log fetch operation."""
        async with get_db_session() as db:
            log_entry = FetchLog(
                id=uuid.uuid4(),
                feed_id=feed_id,
                status_code=status_code,
                duration_ms=duration_ms,
                bytes=bytes_count,
                error=error,
                fetched_at=datetime.utcnow(),
            )
            db.add(log_entry)
            await db.commit()

    async def _publish_new_items_event(self, feed_id: uuid.UUID, count: int):
        """Publish new items event to Redis."""
        redis = await self.get_redis()
        event = {
            "type": "new_items",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {"feed_id": str(feed_id), "count": count},
        }
        await redis.publish("rss:events", str(event))

    async def close(self):
        """Close HTTP client and Redis connection."""
        await self.http_client.aclose()
        if self.redis_client:
            await self.redis_client.close()
