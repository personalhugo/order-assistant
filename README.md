# 🍽️ Assistente de Pedidos com LLM

Chat que recomenda pratos de um cardápio a partir de pedidos em linguagem natural,
no estilo de um app de delivery: *"quero algo leve e barato"*, *"uma opção vegana até R$ 30"*.
A resposta chega em streaming, os pratos sugeridos vão para um carrinho com cálculo de
frete, e o pedido é gravado no banco.

![Tela do chat](docs/screenshot.png)

**Stack:** Python · FastAPI · SQLAlchemy (SQLite/Postgres) · Streamlit · API da Anthropic (Claude)
com saída estruturada · pytest

```
┌──────────────┐  POST /chat/stream (SSE)  ┌───────────────┐  messages.stream  ┌─────────────┐
│  Streamlit   │ ────────────────────────▶ │    FastAPI    │ ────────────────▶ │  LLM (API)  │
│ chat+carrinho│ ◀──── texto aos poucos ── │  + validação  │ ◀── JSON parcial ─│             │
└──────────────┘  /carrinho  /pedidos      └──────┬────────┘  RespostaModelo   └─────────────┘
                                                  │ SQLAlchemy
                                        SQLite (padrão) ou Postgres
                                   restaurantes · pratos · pedidos · itens
```

## Destaques

- **Saída estruturada:** o LLM responde num schema Pydantic (`RespostaModelo`), sem parsing
  frágil de texto livre.
- **Streaming de verdade:** o texto da resposta aparece enquanto o modelo escreve. Como a
  resposta é um JSON, o servidor reinterpreta o JSON incompleto a cada pedaço (com o `jiter`)
  e envia só o trecho novo do campo `resposta` por Server-Sent Events.
- **Sem alucinação de pratos:** a API confere cada `prato_id` sugerido contra o cardápio e
  descarta IDs inventados ou repetidos antes de responder (`app/servico.py`).
- **Carrinho com frete:** cada restaurante cobra sua taxa de entrega, que zera acima de um
  valor mínimo; a API devolve subtotal, frete por restaurante, total e tempo estimado.
- **Pedidos no banco:** `POST /pedidos` grava o pedido com o preço de cada item na hora da
  compra; `GET /pedidos/{id}` consulta.
- **Cardápio no banco:** tabelas criadas e populadas automaticamente a partir de
  `data/cardapio.json` na primeira execução. Troque a `DATABASE_URL` para usar Postgres.
- **Tela responsiva:** cards de pratos em grade (uma coluna no celular, duas no desktop),
  atalhos de pedidos clicáveis, carrinho em janela sobre a conversa e aviso ao adicionar itens.
- **Funciona sem chave de API:** sem `ANTHROPIC_API_KEY`, entra um recomendador heurístico
  por palavras-chave (leve, barato, vegano, "até R$ 25", pizza...). Bom para demo e CI.
- **Testável:** recomendador e banco são injetados via `Depends`; os testes usam um LLM falso
  e um SQLite em memória (nenhuma chamada paga no CI).

## Como rodar

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env             # opcional: coloque sua ANTHROPIC_API_KEY
```

Em um terminal, a API (na primeira vez ela cria `data/pedidos.db` e carrega o cardápio):

```bash
uvicorn app.main:app --reload
```

Em outro, a tela:

```bash
streamlit run frontend/streamlit_app.py
```

- Chat: http://localhost:8501
- Docs interativas da API (Swagger): http://localhost:8000/docs

No Windows, depois de criar o `.venv`, dá para abrir os dois com dois cliques em `iniciar.bat`
(ou `.\iniciar.bat` no terminal, dentro da pasta do projeto).

Testes:

```bash
pytest -q
```

## Endpoints

| Método | Rota                 | Descrição                                                        |
|--------|----------------------|------------------------------------------------------------------|
| GET    | `/health`            | Status e modo atual (`llm` ou `offline`)                         |
| GET    | `/cardapio`          | Lista pratos; filtros opcionais `categoria`, `preco_max`, `tag`  |
| GET    | `/restaurantes`      | Restaurantes com taxa e tempo de entrega                         |
| POST   | `/chat`              | Recebe `mensagem` + `historico`, devolve resposta e pratos       |
| POST   | `/chat/stream`       | Mesmo corpo, resposta em Server-Sent Events                      |
| POST   | `/carrinho/calcular` | Recebe `itens`, devolve subtotal, frete por restaurante e total  |
| POST   | `/pedidos`           | Calcula e grava um pedido (`201`)                                |
| GET    | `/pedidos/{id}`      | Consulta um pedido gravado                                       |

### Chat em streaming

```bash
curl -N localhost:8000/chat/stream -H 'content-type: application/json' \
  -d '{"mensagem": "quero algo leve e barato"}'
```

Cada linha `data:` é um JSON com `tipo`:

```
data: {"tipo":"texto","delta":"Separei "}
data: {"tipo":"texto","delta":"algumas opções..."}
data: {"tipo":"final","resposta":"Separei algumas opções...","sugestoes":[{"prato":{...},"motivo":"..."}],"modo":"llm"}
```

`texto` traz pedaços da resposta conforme o modelo escreve; `final` traz a resposta inteira e os
pratos já validados; `erro` traz `detalhe` se o LLM falhar. O `POST /chat` continua existindo
para quem prefere a resposta completa de uma vez.

### Carrinho e frete

```bash
curl -s localhost:8000/carrinho/calcular -H 'content-type: application/json' \
  -d '{"itens": [{"prato_id": "p05", "quantidade": 2}, {"prato_id": "p21"}]}'
```

```json
{
  "itens": [{"prato": {"id": "p05", "nome": "Sopa de Legumes", "...": "..."}, "quantidade": 2, "subtotal": 36.0}, "..."],
  "fretes": [
    {"restaurante": "Cantina da Vó", "subtotal": 36.0, "taxa": 5.9, "gratis": false, "falta_para_gratis": 44.0},
    {"restaurante": "Açaí do Bairro", "subtotal": 12.9, "taxa": 4.9, "gratis": false, "falta_para_gratis": 67.1}
  ],
  "subtotal": 48.9, "frete": 10.8, "total": 59.7, "tempo_estimado_min": 50
}
```

Regras (em `app/carrinho.py`):

- cada restaurante presente no carrinho cobra a própria `taxa_entrega`;
- a taxa zera quando o subtotal daquele restaurante atinge `FRETE_GRATIS_ACIMA` (padrão R$ 80);
- tempo estimado = maior "preparo do prato mais demorado + tempo de entrega" entre os
  restaurantes, já que as entregas acontecem em paralelo;
- itens repetidos do mesmo prato são somados.

`POST /pedidos` aceita o mesmo corpo (mais `observacoes` opcional) e devolve o pedido gravado com `id`.

## Banco de dados

Tabelas (`app/db.py`): `restaurantes`, `pratos`, `prato_tags` (uma linha por tag, para filtrar
por tag em SQL de forma portável), `pedidos` e `itens_pedido`.

- **SQLite (padrão):** `data/pedidos.db`, criado na primeira execução. Para recomeçar do zero,
  apague o arquivo e suba a API de novo.
- **Postgres:** `pip install "psycopg[binary]"` e, no `.env`,
  `DATABASE_URL=postgresql+psycopg://usuario:senha@localhost:5432/pedidos`. O resto é igual.

Para trocar o cardápio, edite `data/cardapio.json` (restaurantes e pratos) e recrie o banco.
O JSON só é lido quando a tabela `pratos` está vazia.

## Estrutura

```
app/
  main.py          # rotas FastAPI, lifespan (cria/popula o banco) e injeção de dependências
  servico.py       # junta recomendador + cardápio e valida os IDs sugeridos (normal e stream)
  recomendador.py  # RecomendadorClaude (LLM), RecomendadorHeuristico (offline) e extrator do JSON parcial
  carrinho.py      # cálculo de subtotal/frete/tempo e gravação de pedidos
  cardapio.py      # RepositorioCardapio (consultas SQL) e Cardapio (cópia em memória p/ o LLM)
  db.py            # SQLAlchemy: tabelas, engine/sessão e carga inicial do JSON
  models.py        # schemas Pydantic (API, eventos do stream e saída do LLM)
  config.py        # configurações via .env
frontend/
  streamlit_app.py # chat com streaming, cards responsivos, carrinho e finalização do pedido
.streamlit/
  config.toml      # tema da tela (cor de destaque, cantos arredondados)
data/
  cardapio.json    # seed: 8 restaurantes e 22 pratos fictícios
tests/             # pytest: API, stream, carrinho/pedidos, heurística e chamada ao LLM (falsa)
```

## Configuração

| Variável             | Padrão                        | Descrição                                               |
|----------------------|-------------------------------|---------------------------------------------------------|
| `ANTHROPIC_API_KEY`  | —                             | Sem ela, roda no modo offline                           |
| `MODELO_LLM`         | `claude-opus-5-5`             | Modelo usado nas recomendações                          |
| `ESFORCO_LLM`        | `low`                         | `low`/`medium`/`high`: mais esforço = mais lento e caro |
| `MAX_SUGESTOES`      | `3`                           | Máximo de pratos por resposta                           |
| `DATABASE_URL`       | `sqlite:///.../data/pedidos.db` | Qualquer URL aceita pelo SQLAlchemy                   |
| `FRETE_GRATIS_ACIMA` | `80`                          | Subtotal por restaurante que zera o frete               |
| `API_URL`            | `http://localhost:8000`       | Endereço da API usado pelo Streamlit                    |

## Próximos passos

- Deixar o LLM mexer no carrinho pelo chat ("adiciona duas sopas")
- Histórico de pedidos por cliente (login simples)
- Dockerfile + docker-compose para subir API, tela e Postgres juntos

---

Projeto de estudo, sem vínculo com nenhuma empresa de delivery. Pratos e restaurantes são fictícios.
