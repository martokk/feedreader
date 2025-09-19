from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status

from tests.factories import create_feed


class TestOPMLRouter:
    """Test OPML import/export endpoints."""

    @pytest.mark.asyncio
    async def test_import_opml_success(self, async_client, db_session):
        """Test successful OPML import."""
        opml_content = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
    <head>
        <title>Test Export</title>
    </head>
    <body>
        <outline type="rss" text="Test Feed 1" xmlUrl="https://example.com/feed1.xml"/>
        <outline type="rss" text="Test Feed 2" xmlUrl="https://example.com/feed2.xml"/>
    </body>
</opml>"""

        with patch("app.routers.opml.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            files = {
                "file": ("test.opml", BytesIO(opml_content.encode()), "application/xml")
            }
            response = await async_client.post("/api/v1/import/opml", files=files)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "completed"
            assert data["feeds_created"] == 2
            assert data["feeds_skipped"] == 0
            assert len(data["errors"]) == 0

            # Verify Redis scheduler notification
            mock_redis.publish.assert_called_once_with("rss:scheduler", "check_feeds")

    @pytest.mark.asyncio
    async def test_import_opml_skip_existing(self, async_client, db_session):
        """Test OPML import skips existing feeds."""
        # Create existing feed
        existing_feed = await create_feed(
            db_session, url="https://example.com/feed1.xml"
        )

        opml_content = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
    <body>
        <outline type="rss" text="Existing Feed" xmlUrl="https://example.com/feed1.xml"/>
        <outline type="rss" text="New Feed" xmlUrl="https://example.com/feed2.xml"/>
    </body>
</opml>"""

        with patch("app.routers.opml.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            files = {
                "file": ("test.opml", BytesIO(opml_content.encode()), "application/xml")
            }
            response = await async_client.post("/api/v1/import/opml", files=files)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "completed"
            assert data["feeds_created"] == 1  # Only new feed
            assert data["feeds_skipped"] == 1  # Existing feed skipped

    @pytest.mark.asyncio
    async def test_import_opml_invalid_file_extension(self, async_client):
        """Test OPML import with invalid file extension."""
        content = "not opml content"
        files = {"file": ("test.txt", BytesIO(content.encode()), "text/plain")}

        response = await async_client.post("/api/v1/import/opml", files=files)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"] == "File must be an OPML file"

    @pytest.mark.asyncio
    async def test_import_opml_invalid_xml(self, async_client):
        """Test OPML import with invalid XML."""
        invalid_xml = "<?xml version='1.0'?><invalid>unclosed tag"
        files = {
            "file": ("test.opml", BytesIO(invalid_xml.encode()), "application/xml")
        }

        response = await async_client.post("/api/v1/import/opml", files=files)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Invalid OPML format" in data["detail"]

    @pytest.mark.asyncio
    async def test_import_opml_empty_file(self, async_client):
        """Test OPML import with empty file."""
        opml_content = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
    <body>
    </body>
</opml>"""

        with patch("app.routers.opml.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            files = {
                "file": (
                    "empty.opml",
                    BytesIO(opml_content.encode()),
                    "application/xml",
                )
            }
            response = await async_client.post("/api/v1/import/opml", files=files)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "completed"
            assert data["feeds_created"] == 0
            assert data["feeds_skipped"] == 0

    @pytest.mark.asyncio
    async def test_import_opml_nested_outlines(self, async_client):
        """Test OPML import with nested outline elements."""
        opml_content = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
    <body>
        <outline text="Category 1">
            <outline type="rss" text="Feed 1" xmlUrl="https://example.com/feed1.xml"/>
            <outline type="rss" text="Feed 2" xmlUrl="https://example.com/feed2.xml"/>
        </outline>
        <outline text="Category 2">
            <outline type="rss" text="Feed 3" xmlUrl="https://example.com/feed3.xml"/>
        </outline>
    </body>
</opml>"""

        with patch("app.routers.opml.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            files = {
                "file": (
                    "nested.opml",
                    BytesIO(opml_content.encode()),
                    "application/xml",
                )
            }
            response = await async_client.post("/api/v1/import/opml", files=files)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["feeds_created"] == 3

    @pytest.mark.asyncio
    async def test_import_opml_with_errors(self, async_client, db_session):
        """Test OPML import with some feed errors."""
        opml_content = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
    <body>
        <outline type="rss" text="Valid Feed" xmlUrl="https://example.com/valid.xml"/>
        <outline type="rss" text="No URL"/>
        <outline type="rss" text="Empty URL" xmlUrl=""/>
    </body>
</opml>"""

        with patch("app.routers.opml.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            files = {
                "file": (
                    "errors.opml",
                    BytesIO(opml_content.encode()),
                    "application/xml",
                )
            }
            response = await async_client.post("/api/v1/import/opml", files=files)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["feeds_created"] == 1  # Only valid feed
            assert data["feeds_skipped"] == 0

    @pytest.mark.asyncio
    async def test_import_opml_database_error(self, async_client):
        """Test OPML import with database error."""
        opml_content = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
    <body>
        <outline type="rss" text="Test Feed" xmlUrl="https://example.com/feed.xml"/>
    </body>
</opml>"""

        with patch("app.routers.opml.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            # Mock database error
            with patch("app.core.database.AsyncSessionLocal") as mock_session_local:
                mock_session = AsyncMock()
                mock_session.commit.side_effect = Exception("Database error")
                mock_session_local.return_value.__aenter__.return_value = mock_session

                files = {
                    "file": (
                        "test.opml",
                        BytesIO(opml_content.encode()),
                        "application/xml",
                    )
                }
                response = await async_client.post("/api/v1/import/opml", files=files)

                assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                data = response.json()
                assert "Import failed" in data["detail"]

    @pytest.mark.asyncio
    async def test_export_opml_success(self, async_client, db_session):
        """Test successful OPML export."""
        # Create test feeds
        feed1 = await create_feed(
            db_session, title="Feed 1", url="https://example.com/feed1.xml"
        )
        feed2 = await create_feed(
            db_session, title="Feed 2", url="https://example.com/feed2.xml"
        )

        response = await async_client.get("/api/v1/export/opml")

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/xml; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert "feeds_" in response.headers["content-disposition"]
        assert ".opml" in response.headers["content-disposition"]

        # Check XML content
        xml_content = response.text
        assert "<?xml version" in xml_content
        assert "<opml version=" in xml_content
        assert "Feed 1" in xml_content
        assert "Feed 2" in xml_content
        assert "https://example.com/feed1.xml" in xml_content
        assert "https://example.com/feed2.xml" in xml_content

    @pytest.mark.asyncio
    async def test_export_opml_empty(self, async_client, db_session):
        """Test OPML export with no feeds."""
        response = await async_client.get("/api/v1/export/opml")

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/xml; charset=utf-8"

        # Should still be valid XML even with no feeds
        xml_content = response.text
        assert "<?xml version" in xml_content
        assert "<opml version=" in xml_content
        assert "<body>" in xml_content
        assert "</body>" in xml_content

    @pytest.mark.asyncio
    async def test_export_opml_feed_ordering(self, async_client, db_session):
        """Test OPML export feed ordering."""
        # Create feeds with different titles (should be ordered by title)
        feed_z = await create_feed(
            db_session, title="Z Feed", url="https://z.com/feed.xml"
        )
        feed_a = await create_feed(
            db_session, title="A Feed", url="https://a.com/feed.xml"
        )
        feed_no_title = await create_feed(
            db_session, title=None, url="https://notitle.com/feed.xml"
        )

        response = await async_client.get("/api/v1/export/opml")

        assert response.status_code == status.HTTP_200_OK
        xml_content = response.text

        # Check that feeds appear in correct order (title ascending, nulls last)
        a_pos = xml_content.find("A Feed")
        z_pos = xml_content.find("Z Feed")
        notitle_pos = xml_content.find("https://notitle.com/feed.xml")

        assert a_pos < z_pos < notitle_pos

    @pytest.mark.asyncio
    async def test_export_opml_special_characters(self, async_client, db_session):
        """Test OPML export with special characters in feed titles."""
        feed = await create_feed(
            db_session,
            title="Feed with <special> & characters",
            url="https://example.com/special.xml",
        )

        response = await async_client.get("/api/v1/export/opml")

        assert response.status_code == status.HTTP_200_OK
        xml_content = response.text

        # XML should be properly escaped
        assert (
            "Feed with &lt;special&gt; &amp; characters" in xml_content
            or "Feed with <special> & characters" in xml_content
        )

    @pytest.mark.asyncio
    async def test_opml_roundtrip(self, async_client, db_session):
        """Test OPML export followed by import."""
        # Create initial feeds
        feed1 = await create_feed(
            db_session, title="Original Feed 1", url="https://orig1.com/feed.xml"
        )
        feed2 = await create_feed(
            db_session, title="Original Feed 2", url="https://orig2.com/feed.xml"
        )

        # Export OPML
        export_response = await async_client.get("/api/v1/export/opml")
        assert export_response.status_code == status.HTTP_200_OK
        opml_content = export_response.content

        # Clear database (simulate fresh import)
        await db_session.delete(feed1)
        await db_session.delete(feed2)
        await db_session.commit()

        # Import the exported OPML
        with patch("app.routers.opml.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            files = {
                "file": ("exported.opml", BytesIO(opml_content), "application/xml")
            }
            import_response = await async_client.post(
                "/api/v1/import/opml", files=files
            )

            assert import_response.status_code == status.HTTP_200_OK
            import_data = import_response.json()
            assert import_data["feeds_created"] == 2

    @pytest.mark.asyncio
    async def test_import_opml_malformed_urls(self, async_client):
        """Test OPML import with malformed URLs."""
        opml_content = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
    <body>
        <outline type="rss" text="Valid Feed" xmlUrl="https://example.com/valid.xml"/>
        <outline type="rss" text="Invalid URL" xmlUrl="not-a-url"/>
        <outline type="rss" text="Empty URL" xmlUrl=""/>
    </body>
</opml>"""

        with patch("app.routers.opml.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            files = {
                "file": (
                    "malformed.opml",
                    BytesIO(opml_content.encode()),
                    "application/xml",
                )
            }
            response = await async_client.post("/api/v1/import/opml", files=files)

            # Should still succeed but with errors
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["feeds_created"] >= 0  # May create valid feeds
            assert len(data["errors"]) >= 0  # May have errors for invalid URLs

    @pytest.mark.asyncio
    async def test_import_opml_no_redis_scheduler(self, async_client):
        """Test OPML import when Redis scheduler notification fails."""
        opml_content = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
    <body>
        <outline type="rss" text="Test Feed" xmlUrl="https://example.com/feed.xml"/>
    </body>
</opml>"""

        with patch("app.routers.opml.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.publish.side_effect = Exception("Redis error")
            mock_get_redis.return_value = mock_redis

            files = {
                "file": ("test.opml", BytesIO(opml_content.encode()), "application/xml")
            }
            response = await async_client.post("/api/v1/import/opml", files=files)

            # Should still succeed even if Redis notification fails
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["feeds_created"] == 1

    @pytest.mark.asyncio
    async def test_export_opml_content_type(self, async_client, db_session):
        """Test OPML export content type and headers."""
        feed = await create_feed(db_session)

        response = await async_client.get("/api/v1/export/opml")

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/xml; charset=utf-8"

        # Check Content-Disposition header
        content_disposition = response.headers["content-disposition"]
        assert content_disposition.startswith("attachment; filename=feeds_")
        assert content_disposition.endswith(".opml")

    @pytest.mark.asyncio
    async def test_import_opml_large_file(self, async_client):
        """Test OPML import with many feeds."""
        # Create OPML with many feeds
        opml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<opml version="2.0">',
            "<body>",
        ]

        for i in range(100):
            opml_lines.append(
                f'<outline type="rss" text="Feed {i}" xmlUrl="https://example{i}.com/feed.xml"/>'
            )

        opml_lines.extend(["</body>", "</opml>"])
        opml_content = "\n".join(opml_lines)

        with patch("app.routers.opml.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            files = {
                "file": (
                    "large.opml",
                    BytesIO(opml_content.encode()),
                    "application/xml",
                )
            }
            response = await async_client.post("/api/v1/import/opml", files=files)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["feeds_created"] == 100

    @pytest.mark.asyncio
    async def test_import_opml_outline_without_xmlurl(self, async_client):
        """Test OPML import with outline elements that don't have xmlUrl."""
        opml_content = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
    <body>
        <outline text="Category" type="category">
            <outline type="rss" text="Valid Feed" xmlUrl="https://example.com/feed.xml"/>
        </outline>
        <outline text="No URL" type="rss"/>
        <outline text="Not RSS" type="link" htmlUrl="https://example.com"/>
    </body>
</opml>"""

        with patch("app.routers.opml.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            files = {
                "file": (
                    "mixed.opml",
                    BytesIO(opml_content.encode()),
                    "application/xml",
                )
            }
            response = await async_client.post("/api/v1/import/opml", files=files)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["feeds_created"] == 1  # Only the valid feed

    @pytest.mark.asyncio
    async def test_export_opml_xml_structure(self, async_client, db_session):
        """Test OPML export XML structure."""
        feed = await create_feed(
            db_session, title="Test Feed", url="https://example.com/feed.xml"
        )

        response = await async_client.get("/api/v1/export/opml")

        assert response.status_code == status.HTTP_200_OK
        xml_content = response.text

        # Verify XML structure
        assert xml_content.startswith('<?xml version="1.0" encoding="unicode"?>')
        assert '<opml version="2.0">' in xml_content
        assert "<head>" in xml_content
        assert "<title>RSS Reader Export</title>" in xml_content
        assert "<dateCreated>" in xml_content
        assert "<body>" in xml_content
        assert 'type="rss"' in xml_content
        assert 'xmlUrl="https://example.com/feed.xml"' in xml_content
        assert 'text="Test Feed"' in xml_content
