# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Full Stack Development (Docker)

```bash
# Start all services
docker compose up -d

# Stop all services  
docker compose down

# View logs
docker compose logs -f [service_name]
```

### API Development (FastAPI)

```bash
cd api

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run database migrations
alembic upgrade head

# Start API server (development)
uvicorn app.main:app --reload

# Run tests with coverage
pytest

# Run specific test file
pytest tests/test_routers_feeds.py

# Run linting (if available)
# Note: No explicit linting command found - check if ruff or black is available
```

### Worker Development

```bash
cd worker

# Install dependencies
pip install -r requirements.txt

# Start worker
python -m reader_worker.main
```

### Frontend Development (Next.js)

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Run linting
npm run lint
```

### Database Operations

```bash
cd api

# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Backup database (Docker)
docker compose exec postgres pg_dump -U reader reader > backup.sql

# Restore database (Docker)
docker compose exec -T postgres psql -U reader reader < backup.sql
```

## Architecture Overview

### System Components

- **Frontend**: Next.js 15 with React 19, TypeScript, Tailwind CSS, and Radix UI components
- **API**: FastAPI with SQLAlchemy, Alembic, Redis, and PostgreSQL
- **Worker**: Python-based RSS fetcher with scheduler and consumer using Redis job queue
- **Database**: PostgreSQL for persistent data (feeds, items, categories, read states)
- **Cache/Queue**: Redis for job queuing, SSE pub/sub, and caching

### Data Flow

1. User adds RSS feeds through Next.js frontend
2. FastAPI stores feeds in PostgreSQL and publishes SSE events
3. Worker scheduler enqueues fetch jobs to Redis based on feed intervals
4. Worker consumer processes jobs asynchronously with configurable concurrency
5. New items trigger real-time UI updates via Server-Sent Events

### Key Technologies

- **Backend**: FastAPI, SQLAlchemy 2.0, Alembic, AsyncPG, uvloop
- **Frontend**: Next.js 15 with Turbopack, TypeScript, Tailwind CSS 4, Radix UI
- **Content Extraction**: Trafilatura for full article content
- **Real-time**: SSE (Server-Sent Events) for live updates
- **Testing**: pytest with coverage, factory-boy for fixtures

## Architecture Patterns

### Backend Structure (FastAPI)

- `app/core/`: Configuration, database, and Redis connections
- `app/models/`: SQLAlchemy models (Feed, Item, Category, ReadState, FetchLog)
- `app/schemas/`: Pydantic schemas for API serialization
- `app/routers/`: FastAPI routers organized by resource (feeds, items, categories, sse, opml)
- `app/services/`: Business logic (currently empty - logic in routers)

### Frontend Structure (Next.js)

- `src/app/`: App Router with layout.tsx and page.tsx
- `src/components/`: Reusable UI components
    - `dialogs/`: Modal components (AddFeedDialog, CategoryDialog, etc.)
    - `menus/`: Context menu components
    - `ui/`: Shadcn/ui components (button, dialog, dropdown-menu, etc.)
- `src/lib/`: Utilities (api.ts for API calls, sse.ts for real-time events)
- `src/types/`: TypeScript type definitions

### Worker Structure

- `reader_worker/main.py`: Entry point with WorkerManager
- `reader_worker/scheduler.py`: Schedules RSS fetch jobs
- `reader_worker/consumer.py`: Processes fetch jobs from Redis queue
- `reader_worker/fetcher.py`: RSS parsing and content extraction
- `reader_worker/database.py`: Database models mirrored from API

### Database Models

- **Feed**: RSS feed metadata, fetch intervals, categories
- **Item**: Individual RSS items with content extraction
- **Category**: Feed organization (with drag-and-drop support)
- **ReadState**: User reading progress tracking  
- **FetchLog**: Feed fetch history and error tracking

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and modify:

- **Database**: `POSTGRES_*` settings for PostgreSQL connection
- **Redis**: `REDIS_URL` for job queue and caching
- **Worker**: `FETCH_CONCURRENCY`, `PER_HOST_CONCURRENCY`, fetch intervals
- **API**: `UVICORN_WORKERS`, `API_MAX_CONNECTIONS`, CORS origins
- **Content**: `EXTRACTION_ENGINE=trafilatura` for article extraction

### Development vs Production

- Development: Use `docker compose up -d` for full stack
- Individual services: Run API, worker, and frontend separately for debugging
- Production: Deploy behind authentication proxy (no built-in auth)

## Testing

### API Tests

- Located in `api/tests/`
- Uses pytest with async support and factory-boy for fixtures
- Test coverage configured with minimum 80% requirement
- Run with `pytest` from `api/` directory

### Test Categories

- `test_core.py`: Database and Redis connections
- `test_models.py`: SQLAlchemy model validation
- `test_routers_*.py`: API endpoint testing
- `test_integration.py`: End-to-end workflow tests
- `test_deployment.py`: Docker deployment verification

## Real-time Features

### Server-Sent Events (SSE)

- Endpoint: `/api/v1/sse/events`
- Events: `feed_added`, `feed_updated`, `items_updated`, `feed_deleted`
- Used for live UI updates when feeds are modified or new items are fetched
- Heartbeat every 15 seconds to maintain connections

### Worker Concurrency

- Global concurrency limit (`FETCH_CONCURRENCY=10`)
- Per-host concurrency limit (`PER_HOST_CONCURRENCY=2`) to be respectful
- Configurable fetch intervals per feed (default 15 minutes)
- Redis-based job queue with scheduler and consumer separation

## API Design

### REST Endpoints

- `/api/v1/feeds` - CRUD operations for RSS feeds
- `/api/v1/feeds/{id}/items` - Paginated item retrieval
- `/api/v1/feeds/items/{id}` - Individual item details with full content
- `/api/v1/categories` - Feed categorization
- `/api/v1/import/opml` - OPML import for migration
- `/api/v1/export/opml` - OPML export
- `/api/v1/sse/events` - Real-time event stream

### Response Patterns

- Item content includes extracted full article text
- Pagination for item lists
- Category assignments for feeds
- Read state tracking per item
