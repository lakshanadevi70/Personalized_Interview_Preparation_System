from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded only from server-side environment variables."""

    database_url: str = "sqlite:///./careerai.db"
    jwt_secret_key: str = "change-me-for-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    upload_dir: str = "./data/uploads"
    max_upload_bytes: int = 5 * 1024 * 1024
    groq_api_key: str = ""
    hf_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


