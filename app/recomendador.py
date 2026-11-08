"""Recomendadores de pratos.

- `RecomendadorClaude`: usa a API da Anthropic com saída estruturada (Pydantic),
  então a resposta sempre chega no formato `RespostaModelo`.
- `RecomendadorHeuristico`: fallback offline por palavras-chave, usado quando não há
  chave de API configurada (útil para demo, testes e CI).
"""

import re
import unicodedata
from typing import Protocol

import anthropic

from app.cardapio import Cardapio
from app.models import Mensagem, RespostaModelo, Sugestao


class ErroRecomendacao(Exception):
    """Falha ao obter uma recomendação do LLM."""


class Recomendador(Protocol):
    modo: str

    def recomendar(
        self, mensagem: str, historico: list[Mensagem], cardapio: Cardapio
    ) -> RespostaModelo: ...


PROMPT_SISTEMA = """Você é o assistente de pedidos de um app de delivery de comida.
Seu trabalho é recomendar pratos do cardápio abaixo com base no que o cliente pedir
(fome, orçamento, restrições alimentares, vontade do momento).

Regras:
- Recomende SOMENTE pratos que existem no cardápio, usando o `id` exato de cada um.
- Respeite restrições alimentares (vegano, vegetariano, sem glúten, sem lactose) e limites de preço.
- "Leve" normalmente significa poucas calorias (abaixo de ~500 kcal); "barato" significa os mais em conta.
- Sugira no máximo {max_sugestoes} pratos, ordenados do mais adequado para o menos adequado.
- Se nada no cardápio atender ao pedido, devolva `sugestoes` vazio e explique com gentileza.
- Se o cliente só estiver conversando (ex.: "oi"), responda e pergunte o que ele está com vontade de comer.
- Escreva em português do Brasil, em tom simpático e direto, com no máximo 3 frases em `resposta`.
  Não repita preço e descrição de cada prato na `resposta`: os cards do app já mostram isso.

Cardápio (JSON):
{cardapio}"""


class RecomendadorClaude:
    modo = "llm"

    def __init__(self, api_key: str, modelo: str, esforco: str = "low", max_sugestoes: int = 3):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.modelo = modelo
        self.esforco = esforco
        self.max_sugestoes = max_sugestoes

    def recomendar(
        self, mensagem: str, historico: list[Mensagem], cardapio: Cardapio
    ) -> RespostaModelo:
        mensagens = [
            {"role": "user" if m.papel == "usuario" else "assistant", "content": m.conteudo}
            for m in historico
        ]
        mensagens.append({"role": "user", "content": mensagem})
        sistema = PROMPT_SISTEMA.format(
            max_sugestoes=self.max_sugestoes, cardapio=cardapio.como_json_compacto()
        )

        try:
            # beta.messages.parse = saída estruturada + `fallbacks`: se os filtros de
            # segurança recusarem o pedido, a API refaz a chamada em outro modelo.
            resposta = self.client.beta.messages.parse(
                model=self.modelo,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                max_tokens=16000,
                system=sistema,
                messages=mensagens,
                output_config={"effort": self.esforco},
                output_format=RespostaModelo,
            )
        except anthropic.APIConnectionError as e:
            raise ErroRecomendacao("Não foi possível conectar à API do LLM.") from e
        except anthropic.RateLimitError as e:
            raise ErroRecomendacao("Limite de requisições atingido; tente de novo em instantes.") from e
        except anthropic.APIStatusError as e:
            raise ErroRecomendacao(f"Erro da API do LLM (HTTP {e.status_code}).") from e

        if resposta.stop_reason == "refusal":
            raise ErroRecomendacao("O modelo recusou este pedido.")
        if resposta.parsed_output is None:
            raise ErroRecomendacao(f"Resposta incompleta do modelo (stop_reason={resposta.stop_reason}).")
        return resposta.parsed_output


# ---------------------------------------------------------------------------
# Fallback offline
# ---------------------------------------------------------------------------


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower()


# palavra-chave (sem acento) -> tag do cardápio
PALAVRAS_TAG = {
    "leve": "leve",
    "light": "leve",
    "saudavel": "leve",
    "barato": "barato",
    "barata": "barato",
    "economico": "barato",
    "em conta": "barato",
    "proteina": "proteico",
    "proteico": "proteico",
    "caseir": "caseiro",
    "compartilhar": "para_compartilhar",
    "dividir": "para_compartilhar",
    "picante": "picante",
    "apimentad": "picante",
}

# restrições que eliminam pratos que não as atendem
RESTRICOES = {
    "vegan": "vegano",
    "vegetarian": "vegetariano",
    "sem carne": "vegetariano",
    "sem gluten": "sem_gluten",
    "celiac": "sem_gluten",
    "sem lactose": "sem_lactose",
    "intolerante a lactose": "sem_lactose",
}

PALAVRAS_CATEGORIA = {
    "salada": "saladas",
    "bowl": "bowls",
    "poke": "bowls",
    "sopa": "sopas",
    "caldo": "sopas",
    "massa": "massas",
    "macarrao": "massas",
    "lanche": "lanches",
    "burger": "lanches",
    "hamburguer": "lanches",
    "sushi": "japonesa",
    "japones": "japonesa",
    "pizza": "pizzas",
    "doce": "sobremesas",
    "sobremesa": "sobremesas",
    "indian": "indiana",
    "curry": "indiana",
    "marmita": "pratos_feitos",
    "pf": "pratos_feitos",
}

_RE_PRECO = re.compile(r"(?:ate|menos de|no maximo|max)\s*(?:r\$)?\s*(\d+(?:[.,]\d+)?)")


class RecomendadorHeuristico:
    modo = "offline"

    def __init__(self, max_sugestoes: int = 3):
        self.max_sugestoes = max_sugestoes

    def recomendar(
        self, mensagem: str, historico: list[Mensagem], cardapio: Cardapio
    ) -> RespostaModelo:
        texto = _normalizar(mensagem)
        palavras = set(re.findall(r"[a-z]+", texto))

        def menciona(chave: str) -> bool:
            # chaves curtas ("pf") só valem como palavra inteira; as demais, como prefixo/trecho
            return chave in palavras if len(chave) <= 3 else chave in texto

        tags = {tag for chave, tag in PALAVRAS_TAG.items() if menciona(chave)}
        restricoes = {tag for chave, tag in RESTRICOES.items() if menciona(chave)}
        categorias = {cat for chave, cat in PALAVRAS_CATEGORIA.items() if menciona(chave)}
        m = _RE_PRECO.search(texto)
        preco_max = float(m.group(1).replace(",", ".")) if m else None

        candidatos = [
            p
            for p in cardapio.pratos
            if restricoes.issubset(p.tags) and (preco_max is None or p.preco <= preco_max)
        ]
        if categorias:
            candidatos = [p for p in candidatos if p.categoria in categorias] or candidatos

        if not (tags or restricoes or categorias or preco_max):
            return RespostaModelo(
                resposta=(
                    "Oi! Me conta o que você está com vontade de comer: algo leve, barato, "
                    "vegano, uma massa, um lanche...?"
                ),
                sugestoes=[],
            )
        if not candidatos:
            return RespostaModelo(
                resposta="Poxa, não encontrei nada no cardápio que atenda a tudo isso. Quer flexibilizar algum critério?",
                sugestoes=[],
            )

        def pontuacao(p):
            return (-len(tags & set(p.tags)), p.preco if "barato" in tags else p.calorias)

        escolhidos = sorted(candidatos, key=pontuacao)[: self.max_sugestoes]
        criterios = sorted(tags | restricoes | categorias)
        sugestoes = [
            Sugestao(prato_id=p.id, motivo=self._motivo(p, tags | restricoes, preco_max))
            for p in escolhidos
        ]
        return RespostaModelo(
            resposta=f"Separei algumas opções pensando em: {', '.join(criterios) or 'seu orçamento'}.",
            sugestoes=sugestoes,
        )

    @staticmethod
    def _motivo(prato, criterios: set[str], preco_max: float | None) -> str:
        partes = [t.replace("_", " ") for t in prato.tags if t in criterios]
        if preco_max is not None:
            partes.append(f"cabe em R$ {preco_max:.0f}")
        partes.append(f"{prato.calorias} kcal")
        return "Atende: " + ", ".join(partes) + "."
