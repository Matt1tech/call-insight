"""Cloudflare Workers AI client, exposed through its OpenAI-compatible endpoint.

Credentials come from environment variables (or ``backend/.env``) and are never hardcoded.
``get_chat_model`` returns ``None`` when they are missing, which makes the workflow fall
back to replay mode.
"""

from functools import lru_cache

from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

CLOUDFLARE_BASE_URL = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1"


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    cloudflare_account_id: str = ""
    cloudflare_api_token: SecretStr = SecretStr("")
    cloudflare_model: str = ""
    # How structured output is requested: "function_calling", "json_schema" or "json_mode".
    cloudflare_structured_method: str = "function_calling"
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2

    @property
    def configured(self) -> bool:
        return bool(
            self.cloudflare_account_id
            and self.cloudflare_api_token.get_secret_value()
            and self.cloudflare_model
        )


@lru_cache
def get_llm_settings() -> LLMSettings:
    return LLMSettings()


def get_chat_model() -> ChatOpenAI | None:
    """Return the configured chat model, or ``None`` if credentials are not set."""
    settings = get_llm_settings()
    if not settings.configured:
        return None
    return ChatOpenAI(
        model=settings.cloudflare_model,
        api_key=settings.cloudflare_api_token,
        base_url=CLOUDFLARE_BASE_URL.format(account_id=settings.cloudflare_account_id),
        temperature=0,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
