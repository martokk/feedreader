from contextlib import asynccontextmanager

import uvloop
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.redis import close_redis
from .routers import categories, feeds, health, items, opml, sse

# Use uvloop for better async performance
uvloop.install()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("Starting RSS Reader API...")
    yield
    # Shutdown
    print("Shutting down RSS Reader API...")
    await close_redis()


# Create FastAPI app
app = FastAPI(
    title="RSS Reader API",
    description="Minimal self-hosted RSS reader API",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include routers
app.include_router(categories.router, prefix="/api/v1")
app.include_router(feeds.router, prefix="/api/v1")
app.include_router(items.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
app.include_router(sse.router, prefix="/api/v1")
app.include_router(opml.router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "RSS Reader API", "version": "1.0.0"}


@app.get("/api/v1")
async def api_root():
    """API root endpoint."""
    return {
        "message": "RSS Reader API v1",
        "endpoints": {
            "categories": "/api/v1/categories",
            "feeds": "/api/v1/feeds",
            "health": "/api/v1/health",
            "sse": "/api/v1/sse/events",
            "import": "/api/v1/opml/import",
            "export": "/api/v1/opml/export",
        },
    }
