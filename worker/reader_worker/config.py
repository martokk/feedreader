from pydantic_settings import BaseSettings


class WorkerSettings(BaseSettings):
    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "reader"
    postgres_user: str = "reader"
    postgres_password: str = "change-me"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Worker settings
    fetch_default_interval: int = 900  # 15 minutes
    fetch_concurrency: int = 10
    per_host_concurrency: int = 2
    fetch_timeout_seconds: int = 30
    scheduler_tick_seconds: int = 10
    scheduler_batch_size: int = 25
    extraction_engine: str = "trafilatura"  # or "readability"

    # Application
    app_env: str = "production"
    log_level: str = "info"

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = WorkerSettings()
