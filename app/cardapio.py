"""Carregamento e consulta do cardápio em JSON."""

import json
from pathlib import Path

from app.models import Prato


class Cardapio:
    def __init__(self, pratos: list[Prato]):
        self.pratos = pratos
        self._por_id = {p.id: p for p in pratos}

    @classmethod
    def de_arquivo(cls, caminho: Path) -> "Cardapio":
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        return cls([Prato.model_validate(item) for item in dados])

    def buscar(self, prato_id: str) -> Prato | None:
        return self._por_id.get(prato_id)

    def filtrar(
        self,
        categoria: str | None = None,
        preco_max: float | None = None,
        tag: str | None = None,
    ) -> list[Prato]:
        resultado = self.pratos
        if categoria:
            resultado = [p for p in resultado if p.categoria == categoria]
        if preco_max is not None:
            resultado = [p for p in resultado if p.preco <= preco_max]
        if tag:
            resultado = [p for p in resultado if tag in p.tags]
        return resultado

    def como_json_compacto(self) -> str:
        """Versão enxuta do cardápio para colocar no prompt do LLM."""
        return json.dumps(
            [p.model_dump() for p in self.pratos], ensure_ascii=False, separators=(",", ":")
        )
