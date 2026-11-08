"""Configurações lidas de variáveis de ambiente (ou de um arquivo .env)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=RAIZ / ".env", extra="ignore")

    anthropic_api_key: str | None = None
    modelo_llm: str = "claude-opus-5-5"
    esforco_llm: str = "low"  # low | medium | high — "low" basta para um chat de recomendação
    caminho_cardapio: Path = RAIZ / "data" / "cardapio.json"
    max_sugestoes: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
