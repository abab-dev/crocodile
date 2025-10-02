from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    GITHUB_APP_ID: str = Field(
        ..., description="The unique identifier for the GitHub App."
    )
    GITHUB_WEBHOOK_SECRET: str = Field(
        ..., description="The secret used to verify webhook payloads."
    )
    GITHUB_PRIVATE_KEY_PATH: str = Field(
        ..., description="The file path to the app's private key (.pem file)."
    )

    GOOGLE_API_KEY: str = Field(..., description="The API key for OpenAI services.")

    REDIS_URL: str = Field(
        "redis://localhost:6379/0",
        description="The connection URL for the Redis server.",
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
