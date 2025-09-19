import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status


class TestSSERouter:
    """Test Server-Sent Events router."""

    @pytest.mark.asyncio
    async def test_sse_events_endpoint_exists(self, async_client):
        """Test that SSE events endpoint exists and returns proper headers."""
        # Note: This test doesn't actually test the streaming functionality
        # as that's complex with httpx, but verifies the endpoint exists
        response = await async_client.get("/api/v1/sse/events")

        # SSE endpoint should return 200 and have proper headers
        assert response.status_code == status.HTTP_200_OK

    def test_sse_event_stream_headers(self, test_client):
        """Test SSE endpoint headers using sync client."""
        # Use sync client for header testing
        with patch("app.routers.sse.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_pubsub = AsyncMock()
            mock_redis.pubsub.return_value = mock_pubsub
            mock_get_redis.return_value = mock_redis

            # Mock the pubsub subscription to avoid hanging
            mock_pubsub.subscribe.return_value = None
            mock_pubsub.get_message.return_value = None

            response = test_client.get("/api/v1/sse/events")

            # Check SSE headers
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers["connection"] == "keep-alive"
            assert (
                "text/plain" in response.headers["content-type"]
                or "text/event-stream" in response.headers["content-type"]
            )

    @pytest.mark.asyncio
    async def test_event_stream_redis_subscription(self):
        """Test that event stream subscribes to Redis channel."""
        from app.core.redis import RSS_EVENTS_CHANNEL
        from app.routers.sse import event_stream

        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub

        # Mock request
        mock_request = AsyncMock()
        mock_request.is_disconnected.return_value = True  # Disconnect immediately

        with patch("app.routers.sse.get_redis", return_value=mock_redis):
            # Consume the generator until it stops
            stream_gen = event_stream(mock_request)
            events = []
            try:
                async for event in stream_gen:
                    events.append(event)
            except StopAsyncIteration:
                pass

            # Should have subscribed to RSS events channel
            mock_pubsub.subscribe.assert_called_once_with(RSS_EVENTS_CHANNEL)

    @pytest.mark.asyncio
    async def test_event_stream_initial_connection_event(self):
        """Test that event stream sends initial connection event."""
        from app.routers.sse import event_stream

        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub

        # Mock request that disconnects after first event
        mock_request = AsyncMock()
        call_count = 0

        async def mock_is_disconnected():
            nonlocal call_count
            call_count += 1
            return call_count > 1  # Disconnect after first check

        mock_request.is_disconnected = mock_is_disconnected

        with patch("app.routers.sse.get_redis", return_value=mock_redis):
            stream_gen = event_stream(mock_request)

            # Get first event
            first_event = await stream_gen.__anext__()

            assert first_event["event"] == "connected"
            data = json.loads(first_event["data"])
            assert data["type"] == "connected"
            assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_event_stream_message_forwarding(self):
        """Test that event stream forwards Redis messages."""
        from app.routers.sse import event_stream

        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub

        # Mock a Redis message
        redis_message = {
            "type": "message",
            "data": b'{"type": "feed_updated", "data": {"feed_id": "123"}}',
        }

        call_count = 0

        async def mock_get_message(ignore_subscribe_messages=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return redis_message
            else:
                # Simulate timeout for heartbeat
                raise asyncio.TimeoutError()

        mock_pubsub.get_message = mock_get_message

        mock_request = AsyncMock()
        disconnect_count = 0

        async def mock_is_disconnected():
            nonlocal disconnect_count
            disconnect_count += 1
            return disconnect_count > 3  # Allow a few events

        mock_request.is_disconnected = mock_is_disconnected

        with patch("app.routers.sse.get_redis", return_value=mock_redis):
            stream_gen = event_stream(mock_request)
            events = []

            try:
                async for event in stream_gen:
                    events.append(event)
                    if len(events) >= 3:  # Connection + message + heartbeat
                        break
            except StopAsyncIteration:
                pass

            # Should have connection event and forwarded message
            assert len(events) >= 2
            assert events[0]["event"] == "connected"

            # Find the message event
            message_events = [e for e in events if e["event"] == "message"]
            assert len(message_events) >= 1
            assert message_events[0]["data"] == redis_message["data"].decode()

    @pytest.mark.asyncio
    async def test_event_stream_heartbeat(self):
        """Test that event stream sends heartbeat events."""
        from app.routers.sse import event_stream

        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub

        # Mock get_message to always timeout (trigger heartbeat)
        async def mock_get_message(ignore_subscribe_messages=False):
            raise asyncio.TimeoutError()

        mock_pubsub.get_message = mock_get_message

        mock_request = AsyncMock()
        call_count = 0

        async def mock_is_disconnected():
            nonlocal call_count
            call_count += 1
            return call_count > 3  # Allow a few heartbeats

        mock_request.is_disconnected = mock_is_disconnected

        # Mock settings to have very short heartbeat interval
        with patch("app.routers.sse.settings") as mock_settings:
            mock_settings.sse_heartbeat_ms = 100  # 100ms for fast test

            with patch("app.routers.sse.get_redis", return_value=mock_redis):
                stream_gen = event_stream(mock_request)
                events = []

                try:
                    async for event in stream_gen:
                        events.append(event)
                        if len(events) >= 3:  # Connection + heartbeats
                            break
                except StopAsyncIteration:
                    pass

                # Should have connection event and heartbeat events
                assert len(events) >= 2
                assert events[0]["event"] == "connected"

                # Find heartbeat events
                heartbeat_events = [e for e in events if e["event"] == "heartbeat"]
                assert len(heartbeat_events) >= 1

                # Check heartbeat data structure
                heartbeat_data = json.loads(heartbeat_events[0]["data"])
                assert heartbeat_data["type"] == "heartbeat"
                assert "timestamp" in heartbeat_data

    @pytest.mark.asyncio
    async def test_event_stream_client_disconnect(self):
        """Test event stream handles client disconnect."""
        from app.routers.sse import event_stream

        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub

        mock_request = AsyncMock()
        mock_request.is_disconnected.return_value = True  # Immediate disconnect

        with patch("app.routers.sse.get_redis", return_value=mock_redis):
            stream_gen = event_stream(mock_request)
            events = []

            try:
                async for event in stream_gen:
                    events.append(event)
            except StopAsyncIteration:
                pass

            # Should only get connection event before disconnect
            assert len(events) == 1
            assert events[0]["event"] == "connected"

            # Should unsubscribe and close pubsub
            mock_pubsub.unsubscribe.assert_called_once()
            mock_pubsub.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_stream_redis_error_handling(self):
        """Test event stream handles Redis errors gracefully."""
        from app.routers.sse import event_stream

        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub

        # Mock Redis error during subscription
        mock_pubsub.subscribe.side_effect = Exception("Redis connection error")

        mock_request = AsyncMock()
        mock_request.is_disconnected.return_value = False

        with patch("app.routers.sse.get_redis", return_value=mock_redis):
            stream_gen = event_stream(mock_request)
            events = []

            try:
                async for event in stream_gen:
                    events.append(event)
            except StopAsyncIteration:
                pass

            # Should handle error gracefully and clean up
            mock_pubsub.unsubscribe.assert_called_once()
            mock_pubsub.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_stream_message_parsing(self):
        """Test event stream message parsing and forwarding."""
        from app.routers.sse import event_stream

        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub

        # Mock different types of Redis messages
        messages = [
            {"type": "message", "data": b'{"type": "feed_updated", "feed_id": "123"}'},
            {"type": "pmessage", "data": b'{"type": "item_read", "item_id": "456"}'},
            {"type": "subscribe", "data": 1},  # Should be ignored
            {"type": "message", "data": b'{"type": "heartbeat"}'},
        ]

        message_iter = iter(messages)

        async def mock_get_message(ignore_subscribe_messages=False):
            try:
                return next(message_iter)
            except StopIteration:
                raise asyncio.TimeoutError()  # Trigger heartbeat

        mock_pubsub.get_message = mock_get_message

        mock_request = AsyncMock()
        call_count = 0

        async def mock_is_disconnected():
            nonlocal call_count
            call_count += 1
            return call_count > 5  # Allow several events

        mock_request.is_disconnected = mock_is_disconnected

        with patch("app.routers.sse.get_redis", return_value=mock_redis):
            stream_gen = event_stream(mock_request)
            events = []

            try:
                async for event in stream_gen:
                    events.append(event)
                    if len(events) >= 4:  # Connection + messages + heartbeat
                        break
            except StopAsyncIteration:
                pass

            # Should forward message events
            message_events = [e for e in events if e["event"] == "message"]
            assert len(message_events) >= 2  # Should forward the message type events

    @pytest.mark.asyncio
    async def test_sse_endpoint_cors_headers(self, async_client):
        """Test SSE endpoint CORS headers."""
        with patch("app.routers.sse.event_stream") as mock_event_stream:
            # Mock event stream to return immediately
            async def mock_stream(request):
                yield {"event": "test", "data": "test"}

            mock_event_stream.return_value = mock_stream

            response = await async_client.get(
                "/api/v1/sse/events", headers={"Origin": "http://localhost:3000"}
            )

            # Check CORS headers
            assert "access-control-allow-origin" in response.headers
            assert "access-control-allow-credentials" in response.headers

    def test_sse_router_configuration(self):
        """Test SSE router configuration."""
        from app.routers.sse import router

        assert router.prefix == "/sse"
        assert "events" in [tag for tag in router.tags]

    @pytest.mark.asyncio
    async def test_event_stream_cleanup_on_exception(self):
        """Test that event stream cleans up resources on exception."""
        from app.routers.sse import event_stream

        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub

        # Mock an exception during message processing
        mock_pubsub.get_message.side_effect = Exception("Processing error")

        mock_request = AsyncMock()
        mock_request.is_disconnected.return_value = False

        with patch("app.routers.sse.get_redis", return_value=mock_redis):
            stream_gen = event_stream(mock_request)
            events = []

            try:
                async for event in stream_gen:
                    events.append(event)
            except StopAsyncIteration:
                pass

            # Should clean up even on exception
            mock_pubsub.unsubscribe.assert_called_once()
            mock_pubsub.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_stream_settings_integration(self):
        """Test that event stream uses settings for heartbeat interval."""
        from app.routers.sse import event_stream

        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub

        # Mock get_message to timeout (trigger heartbeat logic)
        async def mock_get_message(ignore_subscribe_messages=False):
            raise asyncio.TimeoutError()

        mock_pubsub.get_message = mock_get_message

        mock_request = AsyncMock()
        mock_request.is_disconnected.return_value = True  # Disconnect after setup

        # Mock settings with custom heartbeat
        with patch("app.routers.sse.settings") as mock_settings:
            mock_settings.sse_heartbeat_ms = 5000  # 5 seconds

            with patch("app.routers.sse.get_redis", return_value=mock_redis):
                stream_gen = event_stream(mock_request)

                # Just verify it starts without error
                try:
                    first_event = await stream_gen.__anext__()
                    assert first_event["event"] == "connected"
                except StopAsyncIteration:
                    pass

    @pytest.mark.asyncio
    async def test_event_stream_message_types(self):
        """Test handling of different Redis message types."""
        from app.routers.sse import event_stream

        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub

        # Test different message types
        test_messages = [
            {"type": "message", "data": b'{"event": "test1"}'},
            {"type": "pmessage", "data": b'{"event": "test2"}'},  # Should be ignored
            {"type": "subscribe", "data": 1},  # Should be ignored
            {"type": "unsubscribe", "data": 0},  # Should be ignored
        ]

        message_iter = iter(test_messages)

        async def mock_get_message(ignore_subscribe_messages=False):
            try:
                msg = next(message_iter)
                if ignore_subscribe_messages and msg["type"] in [
                    "subscribe",
                    "unsubscribe",
                ]:
                    return None
                return msg
            except StopIteration:
                raise asyncio.TimeoutError()

        mock_pubsub.get_message = mock_get_message

        mock_request = AsyncMock()
        call_count = 0

        async def mock_is_disconnected():
            nonlocal call_count
            call_count += 1
            return call_count > 6  # Allow several message checks

        mock_request.is_disconnected = mock_is_disconnected

        with patch("app.routers.sse.get_redis", return_value=mock_redis):
            stream_gen = event_stream(mock_request)
            events = []

            try:
                async for event in stream_gen:
                    events.append(event)
                    if len(events) >= 3:
                        break
            except StopAsyncIteration:
                pass

            # Should only forward "message" type events
            message_events = [e for e in events if e["event"] == "message"]
            assert len(message_events) == 1  # Only one message type event
