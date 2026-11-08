import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app, get_cardapio, get_recomendador
from app.models import RespostaModelo, Sugestao


class RecomendadorFalso:
    """Simula o LLM: devolve uma resposta fixa (incluindo um ID inventado)."""

    modo = "llm"

    def __init__(self):
        self.chamadas = []

    def recomendar(self, mensagem, historico, cardapio):
        self.chamadas.append((mensagem, historico))
        return RespostaModelo(
            resposta="Que tal estas?",
            sugestoes=[
                Sugestao(prato_id="p05", motivo="Sopa leve e barata."),
                Sugestao(prato_id="p99", motivo="Prato que não existe."),
                Sugestao(prato_id="p05", motivo="Duplicado."),
                Sugestao(prato_id="p21", motivo="Sobremesa leve."),
            ],
        )


@pytest.fixture
def cardapio():
    return get_cardapio()


@pytest.fixture
def falso():
    return RecomendadorFalso()


@pytest.fixture
def client(falso):
    app.dependency_overrides[get_recomendador] = lambda: falso
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _sem_chave(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
