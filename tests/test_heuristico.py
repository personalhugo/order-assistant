import pytest

from app.recomendador import RecomendadorHeuristico


@pytest.fixture
def rec():
    return RecomendadorHeuristico()


def ids(resposta):
    return [s.prato_id for s in resposta.sugestoes]


def test_leve_e_barato(rec, cardapio):
    r = rec.recomendar("quero algo leve e barato", [], cardapio)
    pratos = [cardapio.buscar(i) for i in ids(r)]
    assert len(pratos) == 3
    assert all({"leve", "barato"} <= set(p.tags) for p in pratos)
    assert [p.preco for p in pratos] == sorted(p.preco for p in pratos)


def test_restricao_vegana_e_respeitada(rec, cardapio):
    r = rec.recomendar("Algo VEGANO pra jantar", [], cardapio)
    assert ids(r)
    assert all("vegano" in cardapio.buscar(i).tags for i in ids(r))


def test_limite_de_preco(rec, cardapio):
    r = rec.recomendar("uma massa até R$ 25", [], cardapio)
    assert ids(r) == ["p07"]


def test_sem_criterio_pergunta_de_volta(rec, cardapio):
    r = rec.recomendar("oi, tudo bem?", [], cardapio)
    assert r.sugestoes == []


def test_nada_atende(rec, cardapio):
    r = rec.recomendar("pizza vegana até 10 reais", [], cardapio)
    assert r.sugestoes == []
