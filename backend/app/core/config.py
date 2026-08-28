"""
Application settings loaded from environment variables / .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenRouter
    OPENROUTER_API_KEY: str = Field(default="", description="OpenRouter API key")
    OPENROUTER_MODEL: str = Field(default="deepseek/deepseek-chat", description="Model identifier")
    OPENROUTER_BASE_URL: str = Field(default="https://openrouter.ai/api/v1")

    # Server
    BACKEND_HOST: str = Field(default="0.0.0.0")
    BACKEND_PORT: int = Field(default=8000)
    BACKEND_RELOAD: bool = Field(default=True)

    # Frontend
    NEXT_PUBLIC_API_URL: str = Field(default="http://localhost:3000")

    # File handling
    MAX_UPLOAD_SIZE_MB: int = Field(default=50)
    UPLOAD_DIR: str = Field(default="./uploads")
    OUTPUT_DIR: str = Field(default="./outputs")

    # Jobs
    JOB_TIMEOUT_SECONDS: int = Field(default=300)

    @property
    def MAX_UPLOAD_SIZE_BYTES(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


settings = Settings()
