"""Testa o RecomendadorClaude sem chamar a API de verdade."""

from types import SimpleNamespace

import pytest

from app.models import Mensagem, RespostaModelo, Sugestao
from app.recomendador import ErroRecomendacao, RecomendadorClaude


def _fake(resposta):
    capturado = {}

    def parse(**kwargs):
        capturado.update(kwargs)
        return resposta

    rec = RecomendadorClaude(api_key="teste", modelo="claude-opus-5-5")
    rec.client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(parse=parse)))
    return rec, capturado


def test_monta_requisicao(cardapio):
    saida = RespostaModelo(resposta="ok", sugestoes=[Sugestao(prato_id="p01", motivo="x")])
    rec, req = _fake(SimpleNamespace(stop_reason="end_turn", parsed_output=saida))

    historico = [Mensagem(papel="usuario", conteudo="oi"), Mensagem(papel="assistente", conteudo="olá")]
    assert rec.recomendar("algo leve", historico, cardapio) is saida

    assert req["model"] == "claude-opus-5-5"
    assert req["output_format"] is RespostaModelo
    assert [m["role"] for m in req["messages"]] == ["user", "assistant", "user"]
    assert req["messages"][-1]["content"] == "algo leve"
    assert '"id":"p22"' in req["system"]


def test_recusa_vira_erro(cardapio):
    rec, _ = _fake(SimpleNamespace(stop_reason="refusal", parsed_output=None))
    with pytest.raises(ErroRecomendacao):
        rec.recomendar("algo", [], cardapio)
