from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/memorywiki"
    redis_url: str = "redis://localhost:6379/0"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "memories"
    minio_use_ssl: bool = False

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    max_retries: int = 3
    job_timeout: int = 300


settings = Settings()
