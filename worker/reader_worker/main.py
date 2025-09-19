import asyncio
import signal
import sys

import uvloop

from .config import settings
from .consumer import JobConsumer
from .scheduler import FeedScheduler


class WorkerManager:
    """Main worker manager that runs scheduler and consumer."""

    def __init__(self):
        self.scheduler = FeedScheduler()
        self.consumer = JobConsumer()
        self.running = False

    async def start(self):
        """Start the worker."""
        self.running = True
        print("Starting RSS Reader Worker...")
        print(
            f"Settings: concurrency={settings.fetch_concurrency}, "
            f"per_host={settings.per_host_concurrency}, "
            f"tick={settings.scheduler_tick_seconds}s"
        )

        # Start scheduler and consumer concurrently
        try:
            await asyncio.gather(
                self.scheduler.start(), self.consumer.start(), return_exceptions=True
            )
        except Exception as e:
            print(f"Worker error: {e}")
        finally:
            await self.stop()

    async def stop(self):
        """Stop the worker gracefully."""
        if not self.running:
            return

        self.running = False
        print("Stopping RSS Reader Worker...")

        # Stop scheduler first (no new jobs)
        await self.scheduler.stop()

        # Stop consumer (finish active jobs)
        await self.consumer.stop()

        print("RSS Reader Worker stopped")

    def handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        print(f"Received signal {signum}, shutting down...")
        asyncio.create_task(self.stop())


async def main():
    """Main entry point."""
    # Use uvloop for better performance
    uvloop.install()

    worker = WorkerManager()

    # Setup signal handlers
    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, lambda s, f: asyncio.create_task(worker.stop()))

    try:
        await worker.start()
    except KeyboardInterrupt:
        print("Received keyboard interrupt")
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
