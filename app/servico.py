"""Orquestra recomendador + cardápio e garante que só pratos reais sejam devolvidos."""

from app.cardapio import Cardapio
from app.models import Mensagem, PratoSugerido, RespostaChat
from app.recomendador import Recomendador


def responder(
    mensagem: str,
    historico: list[Mensagem],
    cardapio: Cardapio,
    recomendador: Recomendador,
    max_sugestoes: int = 3,
) -> RespostaChat:
    bruto = recomendador.recomendar(mensagem, historico, cardapio)

    sugestoes: list[PratoSugerido] = []
    vistos: set[str] = set()
    for s in bruto.sugestoes:
        prato = cardapio.buscar(s.prato_id)
        # descarta IDs inventados pelo modelo e duplicatas
        if prato is None or prato.id in vistos:
            continue
        vistos.add(prato.id)
        sugestoes.append(PratoSugerido(prato=prato, motivo=s.motivo))
        if len(sugestoes) == max_sugestoes:
            break

    return RespostaChat(resposta=bruto.resposta, sugestoes=sugestoes, modo=recomendador.modo)
