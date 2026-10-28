"""Ponto de entrada do WhaleRadar.

Fase 0: busca os preços de BTC, ETH e SOL e manda uma mensagem de teste no Telegram.

Como rodar (dentro da pasta do projeto):
    python src/main.py            -> busca preços e envia para o Telegram
    python src/main.py --so-ver   -> só mostra a mensagem na tela, não envia nada
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from prices import buscar_precos
from telegram_bot import enviar_mensagem

PASTA_PROJETO = Path(__file__).resolve().parent.parent

# Horário de Brasília (UTC-3), para mostrar a hora certa na mensagem.
FUSO_BRASILIA = timezone(timedelta(hours=-3))


def carregar_env():
    """Lê o arquivo .env (se existir) e coloca os valores nas variáveis de ambiente.

    No computador usamos o .env; no GitHub Actions os valores vêm dos Secrets.
    """
    arquivo = PASTA_PROJETO / ".env"
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        # Não sobrescreve algo que já veio de fora (ex.: Secrets do GitHub).
        os.environ.setdefault(chave.strip(), valor.strip())


def carregar_config():
    with open(PASTA_PROJETO / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def formatar_numero(valor, casas=2):
    """Formata no padrão brasileiro: 1234567.8 -> '1.234.567,80'."""
    texto = f"{valor:,.{casas}f}"  # vira '1,234,567.80'
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def montar_mensagem(config, precos):
    agora = datetime.now(FUSO_BRASILIA).strftime("%d/%m/%Y %H:%M")
    linhas = [f"🐋 WhaleRadar — preços agora ({agora})", ""]

    for moeda in config["moedas"]:
        dados = precos.get(moeda["id"])
        if not dados:
            linhas.append(f"{moeda['simbolo']}: preço indisponível no momento")
            continue

        variacao = dados.get("usd_24h_change")
        if variacao is None:
            texto_variacao = ""
        else:
            seta = "🔻" if variacao < 0 else "🔺"
            texto_variacao = f"  {seta} {formatar_numero(variacao, 1)}% em 24h"

        linhas.append(
            f"{moeda['simbolo']}: US$ {formatar_numero(dados['usd'])}"
            f" | R$ {formatar_numero(dados['brl'])}{texto_variacao}"
        )

    linhas += ["", "ℹ️ Informação, não recomendação de investimento."]
    return "\n".join(linhas)


def main():
    so_ver = "--so-ver" in sys.argv

    carregar_env()
    config = carregar_config()

    ids = [m["id"] for m in config["moedas"]]
    precos = buscar_precos(ids, config["moedas_referencia"])
    mensagem = montar_mensagem(config, precos)

    print(mensagem)

    if so_ver:
        print("\n(modo --so-ver: nada foi enviado ao Telegram)")
        return

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        sys.exit(
            "Faltam TELEGRAM_BOT_TOKEN e/ou TELEGRAM_CHAT_ID. "
            "Preencha o arquivo .env (veja .env.example) ou os Secrets do GitHub."
        )

    enviar_mensagem(token, chat_id, mensagem)
    print("\n✅ Mensagem enviada ao Telegram.")


if __name__ == "__main__":
    main()
