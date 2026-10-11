"""Application settings loaded from environment variables."""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from .env file."""
    model_config = SettingsConfigDict(env_file=".env")

    # App
    app_name: str
    app_env: str
    app_version: str
    app_port: str
    app_base_url: str = "http://localhost:8000"
    allowed_origins: str

    # AI Foundary
    api_key_ai_foundary: str
    ai_foundary_endpoint: str
    azure_openai_endpoint: str

    google_api_key: str

    # Redis
    redis_host: str
    redis_port: int
    redis_password: str
    redis_username: str
    ratelimit_redis_db: int

    # PostgreSQL
    db_user: str
    db_pass: str
    db_host: str
    db_port: int
    db_name: str

    # JWT Configuration
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_expire_minutes: int

    # AI and vectors (spec Section 12)
    llm_enabled: bool = True
    qdrant_url: str = ""


env = Settings()
