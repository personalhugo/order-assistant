"""Schemas Pydantic usados pela API e pela saída estruturada do LLM."""

from typing import Literal

from pydantic import BaseModel, Field


class Prato(BaseModel):
    id: str
    nome: str
    restaurante: str
    categoria: str
    descricao: str
    preco: float = Field(gt=0)
    calorias: int = Field(ge=0)
    tempo_preparo_min: int = Field(ge=0)
    tags: list[str] = Field(default_factory=list)


class Mensagem(BaseModel):
    papel: Literal["usuario", "assistente"]
    conteudo: str


class PedidoChat(BaseModel):
    mensagem: str = Field(min_length=1, max_length=500, examples=["quero algo leve e barato"])
    historico: list[Mensagem] = Field(default_factory=list, max_length=20)


# --- Formato que o LLM deve devolver (saída estruturada) ---


class Sugestao(BaseModel):
    prato_id: str = Field(description="ID exato de um prato do cardápio, ex.: 'p05'")
    motivo: str = Field(description="Uma frase curta explicando por que o prato combina com o pedido")


class RespostaModelo(BaseModel):
    resposta: str = Field(description="Mensagem curta e simpática para o cliente, em português")
    sugestoes: list[Sugestao] = Field(description="De 0 a 3 pratos recomendados, do melhor para o pior")


# --- Resposta final da API ---


class PratoSugerido(BaseModel):
    prato: Prato
    motivo: str


class RespostaChat(BaseModel):
    resposta: str
    sugestoes: list[PratoSugerido]
    modo: Literal["llm", "offline"]
