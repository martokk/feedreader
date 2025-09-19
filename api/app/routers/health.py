from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.redis import get_redis

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/liveness")
async def liveness():
    """Liveness check - returns OK when process is running."""
    return {"status": "ok", "message": "API is running"}


@router.get("/readiness")
async def readiness(db: AsyncSession = Depends(get_db)):
    """Readiness check - verifies database and Redis connectivity."""
    checks = {"database": False, "redis": False}

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass

    # Check Redis
    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = True
    except Exception:
        pass

    if not all(checks.values()):
        raise HTTPException(
            status_code=503, detail={"status": "not ready", "checks": checks}
        )

    return {"status": "ready", "checks": checks}
