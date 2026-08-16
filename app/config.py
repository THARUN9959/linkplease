from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    pseudogram_api_key: str = ""
    pseudogram_base_url: str = "https://pseudogram-api.onrender.com"
    database_url: str = "sqlite+aiosqlite:///./linkplease.db"
    max_send_attempts: int = 10
    rate_limit_per_minute: int = 9
    verify_signatures: bool = True
    start_background_workers: bool = True
    send_poll_seconds: float = 0.25
    reconcile_poll_seconds: float = 2.0


settings = Settings()
