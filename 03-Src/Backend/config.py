import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False)


class BaseConfig:
    APP_NAME = "Imperio Motos AI Agent"
    APP_VERSION = "0.1.0"
    APP_ENV = "base"

    SECRET_KEY = os.getenv("SECRET_KEY") or "dev-secret-key-change-me"
    DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///app.db"
    LLM_API_KEY = os.getenv("LLM_API_KEY") or "dev-llm-api-key"
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB") or 10)
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN") or "http://127.0.0.1:5500"
    LOG_LEVEL = os.getenv("LOG_LEVEL") or "INFO"
    LOG_FILE = os.getenv("LOG_FILE") or str(BASE_DIR / "backend.log")
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    JSON_SORT_KEYS = False


class DevelopmentConfig(BaseConfig):
    APP_ENV = "development"


class TestingConfig(BaseConfig):
    APP_ENV = "testing"
    TESTING = True
    SECRET_KEY = os.getenv("SECRET_KEY") or "test-secret-key"
    DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///:memory:"
    LLM_API_KEY = os.getenv("LLM_API_KEY") or "test-llm-api-key"
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN") or "http://127.0.0.1:5500"
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB") or 10)


class ProductionConfig(BaseConfig):
    APP_ENV = "production"

    @classmethod
    def validate(cls):
        missing = []
        for variable in ("SECRET_KEY", "DATABASE_URL", "LLM_API_KEY", "FRONTEND_ORIGIN"):
            if not os.getenv(variable):
                missing.append(variable)

        if missing:
            raise RuntimeError(
                "Missing required environment variables for production: "
                + ", ".join(missing)
            )


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(config_name: str = "development"):
    config_name = (config_name or "development").lower()
    config_class = CONFIG_MAP.get(config_name, DevelopmentConfig)

    if config_name == "production":
        config_class.validate()

    return config_class
