"""Application settings loaded from environment variables."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


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

    # AI
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
    qdrant_collection: str = "unit100_chunks"
    google_genai_use_vertexai: bool = False
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    gemini_model: str = "gemini-3.5-flash"
    gemini_thinking_level: str = "low"
    gemini_embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768
    llm_timeout_seconds: float = 60
    llm_max_retries: int = 2

    # Retrieval and replay (spec Section 12)
    kb_top_k: int = 8
    kb_context_chunks: int = 5
    kb_min_score: float = 0.35
    replay_seconds_per_hour: float = 2.0

    # Demo data package: seed JSON, replay files, corpus, golden sets
    demo_data_dir: str = "local/safeloop-demo-data/data"

    @property
    def demo_data_path(self) -> Path:
        """Absolute demo data directory (relative paths resolve from the repo root)."""
        path = Path(self.demo_data_dir)
        return path if path.is_absolute() else PROJECT_ROOT / path


env = Settings()
