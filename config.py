"""Configuración de la aplicación leída desde variables de entorno."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "ArenaGG"
    app_version: str = "2.0.0"
    database_url: str = "sqlite:///./arenagg.db"
    secret_key: str = "arenagg-clave-de-desarrollo-cambiar-en-produccion-2026"
    token_expiracion_minutos: int = 120
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origen.strip() for origen in self.cors_origins.split(",") if origen.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
