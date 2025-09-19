import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.redis import get_redis
from ..models import Feed

router = APIRouter(tags=["opml"])


@router.post("/import/opml")
async def import_opml(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Import feeds from OPML file."""
    if not file.filename.endswith(".opml"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File must be an OPML file"
        )

    try:
        content = await file.read()
        root = ET.fromstring(content)

        feeds_created = 0
        feeds_skipped = 0
        errors = []

        # Find all outline elements with xmlUrl attribute
        for outline in root.findall(".//outline[@xmlUrl]"):
            feed_url = outline.get("xmlUrl")
            feed_title = outline.get("text") or outline.get("title")

            if not feed_url:
                continue

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
                errors.append(f"Error processing {feed_url}: {str(e)}")

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}",
        )


@router.get("/export/opml")
async def export_opml(db: AsyncSession = Depends(get_db)):
    """Export feeds as OPML file."""
    stmt = select(Feed).order_by(Feed.title.nullslast(), Feed.url)
    result = await db.execute(stmt)
    feeds = result.scalars().all()

    # Create OPML XML structure
    opml = ET.Element("opml", version="2.0")
    head = ET.SubElement(opml, "head")
    ET.SubElement(head, "title").text = "RSS Reader Export"
    ET.SubElement(head, "dateCreated").text = datetime.utcnow().strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )

    body = ET.SubElement(opml, "body")

    for feed in feeds:
        outline = ET.SubElement(body, "outline")
        outline.set("type", "rss")
        outline.set("text", feed.title or feed.url)
        outline.set("title", feed.title or feed.url)
        outline.set("xmlUrl", feed.url)
        outline.set("htmlUrl", feed.url)  # Use same URL for simplicity

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
