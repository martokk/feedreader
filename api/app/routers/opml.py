import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.redis import get_redis
from ..models import Category, Feed

router = APIRouter(tags=["opml"])


async def get_or_create_category(db: AsyncSession, category_name: str) -> Category:
    """Get existing category or create a new one."""
    # Check if category already exists
    stmt = select(Category).where(Category.name == category_name)
    result = await db.execute(stmt)
    existing_category = result.scalar_one_or_none()
    
    if existing_category:
        return existing_category
    
    # Create new category
    category = Category(
        name=category_name,
        description=f"Imported from OPML",
        order=0  # Default order
    )
    db.add(category)
    await db.flush()  # Flush to get the ID
    return category


async def process_outline_group(db: AsyncSession, outline, category_name=None):
    """Process a group of outlines, handling both categories and feeds."""
    feeds_created = 0
    feeds_skipped = 0
    errors = []
    category = None
    
    # If this outline has a text attribute but no xmlUrl, it's a category
    if outline.get("text") and not outline.get("xmlUrl"):
        category_name = outline.get("text")
        try:
            category = await get_or_create_category(db, category_name)
        except Exception as e:
            errors.append(f"Error creating category '{category_name}': {str(e)}")
            return feeds_created, feeds_skipped, errors
    elif category_name:
        # We're processing feeds under a category
        try:
            category = await get_or_create_category(db, category_name)
        except Exception as e:
            errors.append(f"Error getting category '{category_name}': {str(e)}")
            category = None
    
    # Process all child outlines
    for child_outline in outline:
        feed_url = child_outline.get("xmlUrl")
        
        if feed_url:
            # This is a feed
            feed_title = child_outline.get("text") or child_outline.get("title")
            
            try:
                # Check if feed already exists
                stmt = select(Feed).where(Feed.url == feed_url)
                result = await db.execute(stmt)
                existing_feed = result.scalar_one_or_none()

                if existing_feed:
                    feeds_skipped += 1
                    # If feed exists but we have a category, add it to the category
                    if category and category not in existing_feed.categories:
                        existing_feed.categories.append(category)
                    continue

                # Create new feed
                parsed_url = urlparse(feed_url)
                per_host_key = parsed_url.netloc
                next_run_at = datetime.utcnow() + timedelta(seconds=5)

                feed = Feed(
                    url=feed_url,
                    title=feed_title,
                    interval_seconds=900,  # 15 minutes default
                    per_host_key=per_host_key,
                    next_run_at=next_run_at,
                )

                # Add feed to category if we have one
                if category:
                    feed.categories.append(category)

                db.add(feed)
                feeds_created += 1

            except Exception as e:
                errors.append(f"Error processing feed {feed_url}: {str(e)}")
        else:
            # This might be a nested category or group
            child_feeds_created, child_feeds_skipped, child_errors = await process_outline_group(
                db, child_outline, category_name or child_outline.get("text")
            )
            feeds_created += child_feeds_created
            feeds_skipped += child_feeds_skipped
            errors.extend(child_errors)
    
    return feeds_created, feeds_skipped, errors


@router.post("/opml/import")
async def import_opml(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Import feeds from OPML file with category support."""
    if not file.filename or not file.filename.lower().endswith((".opml", ".xml")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File must be an OPML file (.opml or .xml)"
        )

    try:
        content = await file.read()
        
        # Handle both string and bytes content
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        
        root = ET.fromstring(content)

        feeds_created = 0
        feeds_skipped = 0
        errors = []

        # Find the body element (handle potential namespace)
        body = root.find("body")
        if body is None:
            # Try with namespace
            for child in root:
                if child.tag.endswith("body"):
                    body = child
                    break
        
        if body is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OPML format: no body element found"
            )

        # Process all top-level outline elements
        for outline in body:
            feed_url = outline.get("xmlUrl")
            
            if feed_url:
                # This is a direct feed (flat structure)
                feed_title = outline.get("text") or outline.get("title")
                
                try:
                    # Check if feed already exists
                    stmt = select(Feed).where(Feed.url == feed_url)
                    result = await db.execute(stmt)
                    existing_feed = result.scalar_one_or_none()

                    if existing_feed:
                        feeds_skipped += 1
                        continue

                    # Create new feed
                    parsed_url = urlparse(feed_url)
                    per_host_key = parsed_url.netloc
                    next_run_at = datetime.utcnow() + timedelta(seconds=5)

                    feed = Feed(
                        url=feed_url,
                        title=feed_title,
                        interval_seconds=900,  # 15 minutes default
                        per_host_key=per_host_key,
                        next_run_at=next_run_at,
                    )

                    db.add(feed)
                    feeds_created += 1

                except Exception as e:
                    errors.append(f"Error processing feed {feed_url}: {str(e)}")
            else:
                # This might be a category with nested feeds
                outline_feeds_created, outline_feeds_skipped, outline_errors = await process_outline_group(
                    db, outline
                )
                feeds_created += outline_feeds_created
                feeds_skipped += outline_feeds_skipped
                errors.extend(outline_errors)

        await db.commit()

        # Enqueue fetch jobs for new feeds
        if feeds_created > 0:
            redis = await get_redis()
            # Simple approach: trigger scheduler to pick up new feeds
            await redis.publish("rss:scheduler", "check_feeds")

        return {
            "status": "completed",
            "feeds_created": feeds_created,
            "feeds_skipped": feeds_skipped,
            "errors": errors,
        }

    except ET.ParseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OPML format: {str(e)}",
        )
    except Exception as e:
        await db.rollback()
        # Log the full error for debugging
        import logging
        logging.error(f"OPML import error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}",
        )


@router.get("/opml/export")
async def export_opml(db: AsyncSession = Depends(get_db)):
    """Export feeds as OPML file with categories."""
    # Get all categories with their feeds
    categories_stmt = select(Category).order_by(Category.order, Category.name)
    categories_result = await db.execute(categories_stmt)
    categories = categories_result.scalars().all()
    
    # Get uncategorized feeds
    uncategorized_stmt = (
        select(Feed)
        .outerjoin(Category.feeds)
        .where(Category.id.is_(None))
        .order_by(Feed.title.nullslast(), Feed.url)
    )
    uncategorized_result = await db.execute(uncategorized_stmt)
    uncategorized_feeds = uncategorized_result.scalars().all()

    # Create OPML XML structure
    opml = ET.Element("opml", version="2.0")
    head = ET.SubElement(opml, "head")
    ET.SubElement(head, "title").text = "RSS Reader Export"
    ET.SubElement(head, "dateCreated").text = datetime.utcnow().strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )

    body = ET.SubElement(opml, "body")

    # Add categorized feeds
    for category in categories:
        if category.feeds:  # Only create category outline if it has feeds
            category_outline = ET.SubElement(body, "outline")
            category_outline.set("text", category.name)
            if category.description:
                category_outline.set("description", category.description)
            
            for feed in sorted(category.feeds, key=lambda f: f.title or f.url):
                feed_outline = ET.SubElement(category_outline, "outline")
                feed_outline.set("type", "rss")
                feed_outline.set("text", feed.title or feed.url)
                feed_outline.set("title", feed.title or feed.url)
                feed_outline.set("xmlUrl", feed.url)
                feed_outline.set("htmlUrl", feed.url)  # Use same URL for simplicity
                if feed.description:
                    feed_outline.set("description", feed.description)

    # Add uncategorized feeds directly to body
    for feed in uncategorized_feeds:
        outline = ET.SubElement(body, "outline")
        outline.set("type", "rss")
        outline.set("text", feed.title or feed.url)
        outline.set("title", feed.title or feed.url)
        outline.set("xmlUrl", feed.url)
        outline.set("htmlUrl", feed.url)  # Use same URL for simplicity
        if feed.description:
            outline.set("description", feed.description)

    # Convert to string
    ET.indent(opml, space="  ", level=0)
    xml_string = ET.tostring(opml, encoding="unicode", xml_declaration=True)

    return Response(
        content=xml_string,
        media_type="application/xml",
        headers={
            "Content-Disposition": f"attachment; filename=feeds_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.opml"
        },
    )
