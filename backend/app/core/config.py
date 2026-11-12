from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    data_dir: Path = BACKEND_DIR / "data"
    frontend_dir: Path = REPO_DIR / "frontend"

    # Optional: only needed for live LLM analysis (replay mode needs none).
    cloudflare_account_id: str | None = None
    cloudflare_api_token: str | None = None
    cloudflare_model: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
