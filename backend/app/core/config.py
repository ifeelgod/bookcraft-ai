"""
Application settings loaded from environment variables / .env file.
"""
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./bookcraft.db",
        description="Async SQLAlchemy database URL (e.g. postgresql+asyncpg://... or sqlite+aiosqlite:///...)",
    )
    DB_ECHO: bool = Field(default=False, description="SQLAlchemy echo SQL statements")

    # Email Marketing Provider
    EMAIL_MARKETING_PROVIDER: str = Field(
        default="null",
        description="Email marketing provider: 'null', 'webhook', 'sendgrid', 'mailchimp'",
    )
    EMAIL_WEBHOOK_URL: str = Field(default="", description="Webhook URL for lead notification")
    SENDGRID_API_KEY: str = Field(default="", description="SendGrid API key")
    SENDGRID_LIST_ID: str = Field(default="", description="SendGrid contact list ID")
    MAILCHIMP_API_KEY: str = Field(default="", description="Mailchimp API key")
    MAILCHIMP_LIST_ID: str = Field(default="", description="Mailchimp audience/list ID")
    MAILCHIMP_SERVER_PREFIX: str = Field(default="us1", description="Mailchimp server prefix e.g. us1")

    # Demo & Restrictions
    DEMO_MAX_PAGES: int = Field(default=15, description="Maximum pages for demo tier")
    DEMO_MAX_WORDS: int = Field(default=4500, description="Approx word limit for demo tier (15p * 300w)")

    # Security & JWT Auth
    JWT_SECRET_KEY: str = Field(
        default="bookcraft-secret-key-super-secure-jwt-token-2026",
        description="HMAC secret key for signing JWT tokens",
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT hashing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 24 * 30, description="Token validity in minutes (30 days)")

    # Payments (Stripe)
    STRIPE_SECRET_KEY: str = Field(default="sk_test_mock_bookcraft_stripe_secret_key", description="Stripe secret API key")
    STRIPE_PUBLISHABLE_KEY: str = Field(default="pk_test_mock_bookcraft_stripe_publishable_key", description="Stripe publishable API key")
    STRIPE_WEBHOOK_SECRET: str = Field(default="whsec_mock_bookcraft_webhook_secret", description="Stripe webhook signing secret")
    STRIPE_PRICE_ID_PRO_PASS: str = Field(default="price_mock_pro_pass_19", description="Stripe price ID for $19 Pro Pass")
    STRIPE_PRICE_ID_AUTHOR_PRO: str = Field(default="price_mock_author_pro_29", description="Stripe price ID for $29 Author Pro")

    # Payments (PayPal)
    PAYPAL_CLIENT_ID: str = Field(default="sb_mock_bookcraft_paypal_client_id", description="PayPal REST Client ID")
    PAYPAL_CLIENT_SECRET: str = Field(default="sb_mock_bookcraft_paypal_client_secret", description="PayPal REST Client Secret")
    PAYPAL_ENVIRONMENT: str = Field(default="sandbox", description="PayPal environment: 'sandbox' or 'live'")
    PAYPAL_WEBHOOK_ID: str = Field(default="mock_paypal_webhook_id", description="PayPal webhook verification ID")

    # Payment Mode
    PAYMENT_MODE: str = Field(default="test", description="Payment operational mode: 'test' (simulation/sandbox) or 'live'")

    @property
    def MAX_UPLOAD_SIZE_BYTES(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


settings = Settings()
