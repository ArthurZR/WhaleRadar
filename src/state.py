"""Memória do bot: guarda quando foi o último alerta de cada moeda (e a que preço).

Fica num arquivo JSON na pasta .estado/. No GitHub Actions essa pasta é guardada
entre uma execução e outra (veja o radar.yml), senão o bot "esqueceria" tudo.
"""

import json
from datetime import datetime
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent / ".estado" / "ultimos_alertas.json"


def carregar():
    """Retorna {"SOL": {"quando": datetime, "preco": 102.1}, ...} (vazio se não houver memória)."""
    if not ARQUIVO.exists():
        return {}
    bruto = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    return {
        simbolo: {"quando": datetime.fromisoformat(item["quando"]), "preco": item["preco"]}
        for simbolo, item in bruto.items()
    }


def salvar(estado):
    ARQUIVO.parent.mkdir(exist_ok=True)
    bruto = {
        simbolo: {"quando": item["quando"].isoformat(), "preco": item["preco"]}
        for simbolo, item in estado.items()
    }
    ARQUIVO.write_text(json.dumps(bruto, indent=2), encoding="utf-8")


ARQUIVO_ULTIMA_VERIFICACAO = ARQUIVO.parent / "ultima_verificacao.txt"


def carregar_ultima_verificacao():
    """Quando o bot olhou o mercado pela última vez (datetime), ou None se não sabe."""
    if not ARQUIVO_ULTIMA_VERIFICACAO.exists():
        return None
    return datetime.fromisoformat(ARQUIVO_ULTIMA_VERIFICACAO.read_text(encoding="utf-8").strip())


def salvar_ultima_verificacao(quando):
    ARQUIVO.parent.mkdir(exist_ok=True)
    ARQUIVO_ULTIMA_VERIFICACAO.write_text(quando.isoformat(), encoding="utf-8")
