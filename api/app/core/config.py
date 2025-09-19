from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "reader"
    postgres_user: str = "reader"
    postgres_password: str = "change-me"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    uvicorn_workers: int = 2
    api_max_connections: int = 100

    # SSE
    sse_heartbeat_ms: int = 15000

    # Application
    app_env: str = "development"
    log_level: str = "info"
    timezone: str = "UTC"
    frontend_origin: str = "http://localhost:3000"

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def cors_origins(self) -> List[str]:
        if self.app_env == "development":
            # Allow common development origins
            return [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:3001",
                "http://127.0.0.1:3001",
                self.frontend_origin,
            ]
        return [self.frontend_origin]

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
