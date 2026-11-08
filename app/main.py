"""API FastAPI do assistente de pedidos."""

from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Query

from app.cardapio import Cardapio
from app.config import Settings, get_settings
from app.models import PedidoChat, Prato, RespostaChat
from app.recomendador import (
    ErroRecomendacao,
    Recomendador,
    RecomendadorClaude,
    RecomendadorHeuristico,
)
from app.servico import responder

app = FastAPI(
    title="Assistente de Pedidos com LLM",
    description="Recomenda pratos de um cardápio em JSON a partir de pedidos em linguagem natural.",
    version="0.1.0",
)


@lru_cache
def get_cardapio() -> Cardapio:
    return Cardapio.de_arquivo(get_settings().caminho_cardapio)


@lru_cache
def get_recomendador() -> Recomendador:
    s: Settings = get_settings()
    if s.anthropic_api_key:
        return RecomendadorClaude(
            api_key=s.anthropic_api_key,
            modelo=s.modelo_llm,
            esforco=s.esforco_llm,
            max_sugestoes=s.max_sugestoes,
        )
    return RecomendadorHeuristico(max_sugestoes=s.max_sugestoes)


@app.get("/health")
def health(recomendador: Recomendador = Depends(get_recomendador)) -> dict:
    return {"status": "ok", "modo": recomendador.modo}


@app.get("/cardapio", response_model=list[Prato])
def listar_cardapio(
    categoria: str | None = None,
    preco_max: float | None = Query(default=None, gt=0),
    tag: str | None = None,
    cardapio: Cardapio = Depends(get_cardapio),
) -> list[Prato]:
    return cardapio.filtrar(categoria=categoria, preco_max=preco_max, tag=tag)


@app.post("/chat", response_model=RespostaChat)
def chat(
    pedido: PedidoChat,
    cardapio: Cardapio = Depends(get_cardapio),
    recomendador: Recomendador = Depends(get_recomendador),
) -> RespostaChat:
    try:
        return responder(
            pedido.mensagem,
            pedido.historico,
            cardapio,
            recomendador,
            max_sugestoes=get_settings().max_sugestoes,
        )
    except ErroRecomendacao as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
