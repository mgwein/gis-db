import functools

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GISDB_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://gis:gis@localhost:5432/gis"
    test_database_url: str = "postgresql+psycopg://gis:gis@localhost:5432/gis_test"
    log_level: str = "INFO"
    cors_origins: list[str] = ["*"]


@functools.lru_cache
def get_settings() -> Settings:
    return Settings()
