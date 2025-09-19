# RSS Reader - Minimal Self-Hosted RSS Reader

A minimal, snappy, self-hosted RSS reader built with Next.js frontend, FastAPI backend, Python worker, PostgreSQL, and Redis.

## Features

- **Single-user instance** - Designed to be deployed behind your authentication proxy (Authentik, etc.)
- **Real-time updates** - Server-Sent Events (SSE) for live feed updates
- **Asynchronous fetching** - Efficient RSS feed processing with HTTP caching
- **Content extraction** - Full article content extraction using Trafilatura
- **OPML import/export** - Easy migration from other RSS readers
- **Docker-first** - Simple deployment with `docker compose`
- **Responsive UI** - Clean, modern interface built with Tailwind CSS

## Quick Start

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd feedreader
   ```

2. **Copy environment configuration:**

   ```bash
   cp .env.example .env
   ```

3. **Edit `.env` file** with your preferred settings (optional - defaults work for local development)

4. **Start all services:**

   ```bash
   docker compose up -d
   ```

5. **Access the application:**
   - Frontend: <http://localhost:3000>
   - API: <http://localhost:8000>
   - API Documentation: <http://localhost:8000/docs>

## Architecture

### Services

- **frontend** (Next.js) - Web interface on port 3000
- **api** (FastAPI) - REST API on port 8000  
- **worker** - RSS fetcher with scheduler and consumer
- **postgres** - Database for feeds, items, and logs
- **redis** - Job queue, pub/sub, and caching

### Data Flow

1. User adds feed through web UI
2. API stores feed in PostgreSQL
3. Worker scheduler enqueues fetch jobs to Redis
4. Worker consumer processes jobs asynchronously
5. New items trigger SSE events to update UI in real-time

## Configuration

Key environment variables in `.env`:

```bash
# Database
POSTGRES_PASSWORD=your-secure-password

# Worker Settings
FETCH_DEFAULT_INTERVAL=900        # 15 minutes between fetches
FETCH_CONCURRENCY=10             # Total concurrent fetches
PER_HOST_CONCURRENCY=2           # Max concurrent fetches per host
EXTRACTION_ENGINE=trafilatura    # Content extraction engine

# Application
FRONTEND_ORIGIN=http://localhost:3000
```

## Development

### Running Individual Services

**API:**

```bash
cd api
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

**Worker:**

```bash
cd worker  
pip install -r requirements.txt
python -m reader_worker.main
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

### Database Migrations

```bash
cd api
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

## Usage

### Adding Feeds

1. Enter RSS feed URL in the sidebar
2. Click "Add" - feed will be fetched within seconds
3. View items by clicking on the feed

### OPML Import/Export

- **Import:** Use the web interface to upload OPML files
- **Export:** Visit `/api/v1/export/opml` to download your feeds

### Marking Items Read

Click the "Mark Read/Unread" button on any item to track your reading progress.

## API Endpoints

### Feeds

- `GET /api/v1/feeds` - List all feeds
- `POST /api/v1/feeds` - Add new feed
- `DELETE /api/v1/feeds/{id}` - Remove feed

### Items  

- `GET /api/v1/feeds/{id}/items` - Get feed items
- `GET /api/v1/feeds/items/{id}` - Get full item details
- `POST /api/v1/feeds/items/{id}/read` - Mark item read/unread

### OPML

- `POST /api/v1/import/opml` - Import OPML file
- `GET /api/v1/export/opml` - Export feeds as OPML

### Real-time

- `GET /api/v1/sse/events` - Server-Sent Events stream

## Production Deployment

### Behind Reverse Proxy

This application is designed to run behind an authentication proxy like Authentik:

```nginx
location / {
    proxy_pass http://localhost:3000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /api/ {
    proxy_pass http://localhost:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

### Security Considerations

- **No built-in authentication** - Deploy behind your authentication system
- **Database credentials** - Use Docker secrets in production
- **CORS origins** - Set `FRONTEND_ORIGIN` to your actual domain
- **Network isolation** - Only expose ports 3000 and 8000

### Backup

Backup PostgreSQL data:

```bash
docker compose exec postgres pg_dump -U reader reader > backup.sql
```

Restore:

```bash
docker compose exec -T postgres psql -U reader reader < backup.sql
```

## Scaling

### Multiple Workers

To scale feed processing, run additional worker containers:

```yaml
worker-2:
  build: ./worker
  environment:
    # Same config as worker
  depends_on:
    - postgres
    - redis
```

### External Services

Point to external PostgreSQL/Redis by updating connection strings in `.env`:

```bash
POSTGRES_HOST=your-postgres-host
REDIS_URL=redis://your-redis-host:6379/0
```

## Troubleshooting

### Common Issues

**Feeds not updating:**

- Check worker logs: `docker compose logs worker`
- Verify feed URLs are accessible
- Check Redis connectivity

**SSE not working:**

- Ensure reverse proxy doesn't buffer SSE connections
- Check browser developer console for connection errors
- Verify CORS settings

**High memory usage:**

- Reduce `FETCH_CONCURRENCY`
- Tune PostgreSQL connection pool settings
- Monitor with `docker stats`

### Health Checks

- API health: `GET /api/v1/health/readiness`
- Database connectivity included in readiness check
- Worker logs show processing status

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality  
4. Ensure all services start with `docker compose up`
5. Submit pull request

## License

MIT License - see LICENSE file for details.
