from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AIE_", env_file=".env", extra="ignore")
    app_name: str = "Academic Identity Engine"
    database_url: str = "sqlite+aiosqlite:///./aie.db"
    user_agent: str = "AcademicIdentityEngine/1.0 (+contact: admin@example.org)"
    request_timeout: float = 25.0
    max_download_mb: int = 60
    crawl_concurrency: int = 5
    crawl_delay_seconds: float = 1.5
    default_language: str = "eng"
    enable_semantic: bool = False
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"

settings = Settings()
