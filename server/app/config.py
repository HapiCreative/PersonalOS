from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/personalos"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/personalos"

    # Auth
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    # Redis (for ARQ job queuing)
    redis_url: str = "redis://localhost:6379"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = {"env_prefix": "POS_", "env_file": ".env"}


settings = Settings()
