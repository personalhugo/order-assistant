def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "modo": "llm"}


def test_cardapio_filtros(client):
    todos = client.get("/cardapio").json()
    assert len(todos) == 22
    baratos_veganos = client.get("/cardapio", params={"tag": "vegano", "preco_max": 20}).json()
    assert baratos_veganos
    assert all("vegano" in p["tags"] and p["preco"] <= 20 for p in baratos_veganos)


def test_chat_descarta_ids_invalidos_e_duplicados(client, falso):
    r = client.post("/chat", json={"mensagem": "quero algo leve e barato"})
    assert r.status_code == 200
    corpo = r.json()
    assert [s["prato"]["id"] for s in corpo["sugestoes"]] == ["p05", "p21"]
    assert corpo["sugestoes"][0]["prato"]["nome"] == "Sopa de Legumes"
    assert corpo["modo"] == "llm"


def test_chat_repassa_historico(client, falso):
    historico = [
        {"papel": "usuario", "conteudo": "oi"},
        {"papel": "assistente", "conteudo": "Oi! O que vai ser hoje?"},
    ]
    client.post("/chat", json={"mensagem": "algo vegano", "historico": historico})
    mensagem, hist = falso.chamadas[0]
    assert mensagem == "algo vegano"
    assert [m.papel for m in hist] == ["usuario", "assistente"]


def test_chat_valida_entrada(client):
    assert client.post("/chat", json={"mensagem": ""}).status_code == 422


def test_chat_erro_do_llm_vira_502(client, falso):
    from app.recomendador import ErroRecomendacao

    def explode(*_):
        raise ErroRecomendacao("fora do ar")

    falso.recomendar = explode
    r = client.post("/chat", json={"mensagem": "pizza"})
    assert r.status_code == 502
    assert r.json()["detail"] == "fora do ar"
