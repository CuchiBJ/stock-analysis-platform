from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    database_url: str = Field(..., env="DATABASE_URL")
    polygon_api_key: str = Field(..., env="POLYGON_API_KEY")
    cors_origins: str = Field("http://localhost:3000", env="CORS_ORIGINS")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
