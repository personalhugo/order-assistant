"""Tela de chat em Streamlit que conversa com a API FastAPI."""

import os

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")
EXEMPLOS = [
    "Quero algo leve e barato",
    "Uma opção vegana até R$ 30",
    "Tô com muita fome, quero algo caseiro",
    "Algo pra dividir com amigos",
]

st.set_page_config(page_title="Assistente de Pedidos", page_icon="🍽️", layout="centered")


def chamar_api(mensagem: str, historico: list[dict]) -> dict:
    payload = {
        "mensagem": mensagem,
        # só o texto vai para a API; mantém as últimas 10 mensagens de contexto
        "historico": [{"papel": m["papel"], "conteudo": m["conteudo"]} for m in historico[-10:]],
    }
    r = httpx.post(f"{API_URL}/chat", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def mostrar_sugestoes(sugestoes: list[dict]) -> None:
    for s in sugestoes:
        p = s["prato"]
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            col1.markdown(f"**{p['nome']}**  \n{p['restaurante']}")
            col2.markdown(f"### R$ {p['preco']:.2f}".replace(".", ","))
            st.caption(p["descricao"])
            st.markdown(f"💡 {s['motivo']}")
            tags = " · ".join(t.replace("_", " ") for t in p["tags"])
            st.caption(f"🔥 {p['calorias']} kcal · ⏱️ {p['tempo_preparo_min']} min · {tags}")


if "mensagens" not in st.session_state:
    st.session_state.mensagens = []

with st.sidebar:
    st.header("🍽️ Assistente de Pedidos")
    st.write("Diga o que você quer comer e o assistente sugere pratos do cardápio.")
    try:
        modo = httpx.get(f"{API_URL}/health", timeout=5).json()["modo"]
        st.success("API conectada · " + ("LLM" if modo == "llm" else "modo offline (sem chave)"))
    except httpx.HTTPError:
        st.error(f"API fora do ar em {API_URL}")
    st.subheader("Experimente")
    for exemplo in EXEMPLOS:
        if st.button(exemplo, use_container_width=True):
            st.session_state.pendente = exemplo
    if st.button("🗑️ Limpar conversa", use_container_width=True):
        st.session_state.mensagens = []
        st.rerun()

st.title("O que vai ser hoje?")

for m in st.session_state.mensagens:
    with st.chat_message("user" if m["papel"] == "usuario" else "assistant"):
        st.markdown(m["conteudo"])
        mostrar_sugestoes(m.get("sugestoes", []))

entrada = st.chat_input("Ex.: quero algo leve e barato") or st.session_state.pop("pendente", None)

if entrada:
    historico = list(st.session_state.mensagens)
    st.session_state.mensagens.append({"papel": "usuario", "conteudo": entrada})
    with st.chat_message("user"):
        st.markdown(entrada)

    with st.chat_message("assistant"):
        with st.spinner("Olhando o cardápio..."):
            try:
                dados = chamar_api(entrada, historico)
            except httpx.HTTPStatusError as e:
                detalhe = e.response.json().get("detail", e.response.text)
                dados = {"resposta": f"⚠️ Erro: {detalhe}", "sugestoes": []}
            except httpx.HTTPError:
                dados = {"resposta": f"⚠️ Não consegui falar com a API em {API_URL}.", "sugestoes": []}
        st.markdown(dados["resposta"])
        mostrar_sugestoes(dados["sugestoes"])

    st.session_state.mensagens.append(
        {"papel": "assistente", "conteudo": dados["resposta"], "sugestoes": dados["sugestoes"]}
    )
