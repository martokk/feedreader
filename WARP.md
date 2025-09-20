# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Development Commands

### Full Stack Development (Docker - Recommended)
```bash
# Start all services
docker compose up -d

# Stop all services  
docker compose down

# CRITICAL: Build containers after ANY Python code changes
# Docker Compose does NOT automatically rebuild containers when code changes
docker compose build
docker compose up -d

# Or rebuild specific services
docker compose build api worker
docker compose up api worker -d

# View logs
docker compose logs -f [service_name]
```

### Individual Service Development

**API (FastAPI):**
```bash
cd api

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run database migrations
alembic upgrade head

# Start API server (development mode)
uvicorn app.main:app --reload

# Run tests with coverage (minimum 80% required)
pytest

# Run specific test file
pytest tests/test_routers_feeds.py

# Create new database migration
alembic revision --autogenerate -m "Description"
```

**Worker:**
```bash
cd worker

# Install dependencies  
pip install -r requirements.txt

# Start worker
python -m reader_worker.main
```

**Frontend (Next.js):**
```bash
cd frontend

# Install dependencies
npm install

# Start development server (with Turbopack)
npm run dev

# Build for production (with Turbopack)
npm run build

# Start production server
npm start

# Run linting
npm run lint
```

### Database Operations
```bash
cd api

# Backup database (Docker)
docker compose exec postgres pg_dump -U reader reader > backup.sql

# Restore database (Docker)
docker compose exec -T postgres psql -U reader reader < backup.sql
```

## Architecture Overview

### System Components
- **Frontend**: Next.js 15 with React 19, TypeScript, Tailwind CSS 4, and Radix UI components
- **API**: FastAPI with SQLAlchemy 2.0, Alembic migrations, uvloop for performance
- **Worker**: Async RSS fetcher with scheduler and consumer using Redis job queue
- **Database**: PostgreSQL for persistent data (feeds, items, categories, read states)
- **Cache/Queue**: Redis for job queuing, Server-Sent Events pub/sub, and caching

### Data Flow Architecture
1. **User adds RSS feeds** through Next.js frontend
2. **FastAPI stores feeds** in PostgreSQL and publishes SSE events  
3. **Worker scheduler** enqueues fetch jobs to Redis based on feed intervals
4. **Worker consumer** processes jobs asynchronously with configurable concurrency limits
5. **New items trigger real-time UI updates** via Server-Sent Events (SSE)

### Key Technologies & Patterns
- **Content Extraction**: Trafilatura for full article content extraction
- **Real-time Updates**: Server-Sent Events (no WebSockets) for live feed updates
- **Async Processing**: Full async/await patterns throughout with uvloop
- **Testing**: pytest with async support, factory-boy fixtures, 80% coverage requirement
- **Authentication**: Single-user instance designed to run behind auth proxy (Authentik, etc.)

## Code Structure

### Backend Architecture (FastAPI)
- `api/app/core/`: Configuration, database connections, Redis client
- `api/app/models/`: SQLAlchemy 2.0 models (Feed, Item, Category, ReadState, FetchLog, UserSettings)
- `api/app/schemas/`: Pydantic schemas for API serialization/validation
- `api/app/routers/`: FastAPI routers organized by resource:
  - `feeds.py`: CRUD operations for RSS feeds
  - `items.py`: Item retrieval and read state management
  - `categories.py`: Feed categorization with drag-and-drop support
  - `sse.py`: Server-Sent Events for real-time updates
  - `opml.py`: OPML import/export functionality
  - `health.py`: Health checks and readiness probes

### Frontend Architecture (Next.js App Router)
- `src/app/`: App Router with layout.tsx and page.tsx
- `src/components/`: 
  - `dialogs/`: Modal components (AddFeedDialog, CategoryDialog, FeedSettingsDialog)
  - `menus/`: Context menu components (FeedMenu)
  - `ui/`: Shadcn/ui components (button, dialog, dropdown-menu, etc.)
- `src/lib/`: Core utilities
  - `api.ts`: API client with TypeScript types
  - `sse.ts`: Server-Sent Events client for real-time updates
  - `utils.ts`: General utilities and class name helpers
- `src/types/`: TypeScript type definitions

### Worker Architecture
- `worker/reader_worker/main.py`: Entry point with WorkerManager coordination
- `worker/reader_worker/scheduler.py`: Schedules RSS fetch jobs based on intervals
- `worker/reader_worker/consumer.py`: Processes fetch jobs from Redis queue
- `worker/reader_worker/fetcher.py`: RSS parsing with feedparser and content extraction
- `worker/reader_worker/database.py`: Database models (mirrors API models)

### Database Models & Relationships
- **Feed**: RSS feed metadata, fetch intervals, category assignments
- **Item**: Individual RSS items with extracted full content  
- **Category**: Feed organization with drag-and-drop ordering
- **ReadState**: Per-item reading progress tracking
- **FetchLog**: Feed fetch history, error tracking, and statistics
- **UserSettings**: User preferences and configuration

## Configuration & Environment

### Critical Environment Variables (.env)
```bash
# Database connection
POSTGRES_HOST=postgres
POSTGRES_PASSWORD=change-me

# Worker performance tuning
FETCH_DEFAULT_INTERVAL=900        # 15 minutes between fetches
FETCH_CONCURRENCY=10             # Total concurrent fetches across all hosts
PER_HOST_CONCURRENCY=2           # Max concurrent fetches per host (be respectful)
EXTRACTION_ENGINE=trafilatura    # Content extraction engine

# API configuration
UVICORN_WORKERS=2                # API server workers
FRONTEND_ORIGIN=http://localhost:3000  # CORS configuration
```

### Development vs Production
- **Development**: Use `docker compose up -d` for full integrated stack
- **Individual Services**: Run services separately for debugging and faster iteration
- **Production**: Deploy behind authentication proxy, no built-in authentication
- **Testing**: pytest with 80% coverage requirement, async test support

## Real-time Features

### Server-Sent Events (SSE)
- **Endpoint**: `/api/v1/sse/events`
- **Event Types**: `feed_added`, `feed_updated`, `items_updated`, `feed_deleted`
- **Purpose**: Live UI updates when feeds are modified or new items are fetched
- **Implementation**: sse-starlette with 15-second heartbeats

### Worker Concurrency Controls
- **Global Limit**: `FETCH_CONCURRENCY=10` total concurrent fetches
- **Per-Host Limit**: `PER_HOST_CONCURRENCY=2` to be respectful to feed servers  
- **Configurable Intervals**: Each feed can have custom fetch intervals (default 15 minutes)
- **Redis Queue**: Separates job scheduling from job processing for scalability

## API Design Patterns

### REST Endpoints Structure
- `/api/v1/feeds` - Feed CRUD with category assignment
- `/api/v1/feeds/{id}/items` - Paginated item retrieval  
- `/api/v1/feeds/items/{id}` - Full item details with extracted content
- `/api/v1/categories` - Feed organization and ordering
- `/api/v1/import/opml` - OPML import for RSS reader migration
- `/api/v1/export/opml` - OPML export  
- `/api/v1/sse/events` - Real-time event stream

### Response Patterns
- **Item Content**: Includes extracted full article text via Trafilatura
- **Pagination**: Used for item lists to handle large feeds efficiently
- **Category Support**: Feeds can be organized in categories with drag-and-drop ordering
- **Read State Tracking**: Per-item read/unread status with toggle functionality

## Important Development Notes

### Docker Rebuild Requirement
**CRITICAL**: Docker Compose does NOT automatically update containers when Python code changes. You MUST run `docker compose build` after any changes to API or Worker code, then restart the services.
- When completing a task that updated code, and you are ready for the user to review, always run this command after you complete changes so I can test it `docker compose down frontend && docker compose up -d --build`

### Testing Philosophy
- 80% minimum test coverage enforced
- Async test support with pytest-asyncio
- Factory-boy for creating test fixtures
- Integration tests verify full workflow from API to worker
- Docker deployment tests ensure production readiness

### Single-User Design
This application is architected as a single-user RSS reader designed to run behind an authentication proxy (like Authentik). There is no built-in user authentication - deploy it behind your existing auth system.