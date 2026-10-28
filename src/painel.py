"""Painel visual (Fase 6): prepara o site que vai para o GitHub Pages.

O visual fica em painel/ (HTML, CSS e JS feitos à mão). Aqui só geramos o
dados.json com a foto do momento: preços, termômetros, humor do mercado,
radar e últimos alertas. O GitHub Actions publica a pasta site/ inteira.
"""

import json
import shutil
from pathlib import Path

from mensagens import humor_do_mercado

PASTA_PROJETO = Path(__file__).resolve().parent.parent
PASTA_VISUAL = PASTA_PROJETO / "painel"
PASTA_SITE = PASTA_PROJETO / "site"

NOMES_PERFIL = {"longo_prazo": "comprar e segurar", "curto_prazo": "comprar e vender"}


def _encurtar(precos, pontos=84):
    """Reduz a linha de 7 dias (168 pontos, 1 por hora) para ~84, suficiente para o gráfico."""
    if len(precos) <= pontos:
        return precos
    passo = len(precos) / pontos
    return [precos[int(i * passo)] for i in range(pontos)] + [precos[-1]]


def gerar(config, mercado, precos_brl, termometros, medo, movimentos, historico, agora):
    """Escreve site/ (visual + dados.json). Devolve a pasta gerada."""
    moedas = []
    for moeda in config["moedas"]:
        dados = mercado.get(moeda["id"])
        if not dados:
            continue
        termometro = termometros.get(moeda["simbolo"])
        moedas.append({
            "id": moeda["id"],
            "simbolo": moeda["simbolo"],
            "nome": dados.get("name", moeda["simbolo"]),
            "emoji": moeda["emoji"],
            "perfil": NOMES_PERFIL.get(moeda["perfil"], moeda["perfil"]),
            "preco_usd": dados["current_price"],
            "preco_brl": precos_brl.get(moeda["id"]),
            "var_1h": dados.get("price_change_percentage_1h_in_currency"),
            "var_24h": dados.get("price_change_percentage_24h_in_currency"),
            "var_7d": dados.get("price_change_percentage_7d_in_currency"),
            "linha_7d": _encurtar((dados.get("sparkline_in_7d") or {}).get("price") or []),
            "termometro": None if not termometro else {
                "pontos": termometro["pontos"],
                "total": termometro["total"],
                "interesse": termometro["interesse"],
                "leitura": termometro["leitura"],
                "itens": [{"ok": ok, "texto": texto} for ok, texto in termometro["itens"]],
            },
        })

    humor = None
    if medo:
        emoji, texto = humor_do_mercado(medo["valor"])
        humor = {"valor": medo["valor"], "texto": texto, "emoji": emoji}

    dados_painel = {
        "atualizado_em": agora.isoformat(),
        "humor": humor,
        "moedas": moedas,
        "radar": movimentos,
        "alertas": historico[:40],
    }

    # Recria a pasta do site do zero: visual + dados.
    if PASTA_SITE.exists():
        shutil.rmtree(PASTA_SITE)
    shutil.copytree(PASTA_VISUAL, PASTA_SITE)
    (PASTA_SITE / "dados.json").write_text(json.dumps(dados_painel, ensure_ascii=False), encoding="utf-8")
    return PASTA_SITE
