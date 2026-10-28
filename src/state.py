"""Memória do bot: último alerta de cada moeda, última checagem, histórico de alertas e último resumo.

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


ARQUIVO_HISTORICO = ARQUIVO.parent / "historico_alertas.json"
ARQUIVO_ULTIMO_RESUMO = ARQUIVO.parent / "ultimo_resumo.txt"


def carregar_historico():
    """Lista dos últimos alertas enviados (mais recente primeiro), para o painel e o resumo."""
    if not ARQUIVO_HISTORICO.exists():
        return []
    return json.loads(ARQUIVO_HISTORICO.read_text(encoding="utf-8"))


def registrar_alerta(historico, alerta, agora, maximo=100, dias=30):
    """Põe um alerta no começo do histórico e descarta os velhos (mais de 30 dias ou além de 100)."""
    historico.insert(0, {**alerta, "quando": agora.isoformat()})
    limite = agora.timestamp() - dias * 24 * 3600
    historico[:] = [a for a in historico[:maximo] if datetime.fromisoformat(a["quando"]).timestamp() >= limite]


def salvar_historico(historico):
    ARQUIVO.parent.mkdir(exist_ok=True)
    ARQUIVO_HISTORICO.write_text(json.dumps(historico, ensure_ascii=False, indent=2), encoding="utf-8")


def carregar_ultimo_resumo():
    """Data (AAAA-MM-DD, horário de Brasília) do último resumo diário enviado, ou None."""
    if not ARQUIVO_ULTIMO_RESUMO.exists():
        return None
    return ARQUIVO_ULTIMO_RESUMO.read_text(encoding="utf-8").strip()


def salvar_ultimo_resumo(data):
    ARQUIVO.parent.mkdir(exist_ok=True)
    ARQUIVO_ULTIMO_RESUMO.write_text(data, encoding="utf-8")
