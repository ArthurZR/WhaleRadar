"""Ponto de entrada do WhaleRadar.

Fase 1: olha BTC, ETH e SOL e manda um alerta no Telegram quando alguma cai além
dos limites do config.yaml (respeitando o anti-spam).

Como rodar (dentro da pasta do projeto):
    python src/main.py             -> verifica quedas e envia os alertas
    python src/main.py --teste     -> envia uma mensagem com os preços atuais (ignora as regras)
    python src/main.py --so-ver    -> só mostra na tela, não envia nada (combina com --teste)
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

import state
from alerts import calcular_indicadores, pode_alertar, quedas_detectadas
from mensagens import montar_alerta, montar_resumo
from prices import buscar_mercado, buscar_precos_brl
from telegram_bot import enviar_mensagem

PASTA_PROJETO = Path(__file__).resolve().parent.parent


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


def main():
    modo_teste = "--teste" in sys.argv
    so_ver = "--so-ver" in sys.argv

    carregar_env()
    config = carregar_config()

    # .strip() remove espaços e quebras de linha coladas sem querer junto com o valor.
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not so_ver and (not token or not chat_id):
        sys.exit(
            "Faltam TELEGRAM_BOT_TOKEN e/ou TELEGRAM_CHAT_ID. "
            "Preencha o arquivo .env (veja .env.example) ou os Secrets do GitHub."
        )

    ids = [m["id"] for m in config["moedas"]]
    mercado = buscar_mercado(ids)
    precos_brl = buscar_precos_brl(ids)

    def enviar(texto):
        print(texto, "\n")
        if not so_ver:
            enviar_mensagem(token, chat_id, texto)

    if modo_teste:
        enviar(montar_resumo(config, mercado, precos_brl))
        return

    memoria = state.carregar()
    agora = datetime.now(timezone.utc)

    for moeda in config["moedas"]:
        simbolo = moeda["simbolo"]
        dados = mercado.get(moeda["id"])
        if not dados:
            print(f"{simbolo}: sem dados da CoinGecko agora, pulando.")
            continue

        indicadores = calcular_indicadores(dados)
        quedas = quedas_detectadas(indicadores, config["limites_queda"])
        if not quedas:
            print(f"{simbolo}: nenhuma queda além dos limites.")
            continue

        preco = dados["current_price"]
        if not pode_alertar(memoria.get(simbolo), preco, agora, config["anti_spam"]):
            print(f"{simbolo}: queda detectada ({', '.join(quedas)}), mas o anti-spam segurou.")
            continue

        enviar(montar_alerta(moeda, dados, precos_brl.get(moeda["id"]), indicadores, quedas))
        # Só anota na memória depois que a mensagem foi enviada com sucesso.
        if not so_ver:
            memoria[simbolo] = {"quando": agora, "preco": preco}

    if not so_ver:
        state.salvar(memoria)


if __name__ == "__main__":
    main()
