from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    database_url: str = Field(..., env="DATABASE_URL")
    polygon_api_key: str = Field(..., env="POLYGON_API_KEY")
    cors_origins: str = Field("http://localhost:3000", env="CORS_ORIGINS")
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")

    # IBKR Flex Web Service — optional. When both are set, the journal can
    # auto-sync executed trades (POST /journal/sync-ibkr and the nightly
    # scheduler job). Generate in IBKR Account Management → Reports → Flex
    # Queries → Flex Web Service (token) + an Activity Flex Query with the
    # Trades/Executions section (query id).
    ibkr_flex_token: Optional[str] = Field(None, env="IBKR_FLEX_TOKEN")
    ibkr_flex_query_id: Optional[str] = Field(None, env="IBKR_FLEX_QUERY_ID")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
