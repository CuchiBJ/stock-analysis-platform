from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    database_url: str = Field(..., env="DATABASE_URL")
    polygon_api_key: str = Field(..., env="POLYGON_API_KEY")
    cors_origins: str = Field("http://localhost:3000", env="CORS_ORIGINS")
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")

    # Anthropic API key for the in-app chat (read-only DB Q&A via tool use).
    anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
