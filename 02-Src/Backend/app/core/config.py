from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    DB_HOST: str = Field(min_length=1)
    DB_PORT: int = Field(ge=1, le=65535)
    DB_NAME: str = Field(min_length=1)
    DB_USER: str = Field(min_length=1)
    DB_PASSWORD: str
    CORS_ORIGINS: str = "http://localhost:5500,http://127.0.0.1:5500"
    MAX_UPLOAD_MB: int = Field(default=10, ge=1)
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Path = BACKEND_DIR / "backend.log"

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if "*" in origins:
            raise ValueError("CORS_ORIGINS no puede incluir '*' si las credenciales estan activas.")
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()