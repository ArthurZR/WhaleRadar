"""Ponto de entrada do WhaleRadar.

Olha BTC, ETH e SOL e manda no Telegram:
- alerta de queda (com "por quê", notícia e termômetro de compra de 0 a 5) quando alguma cai além dos limites;
- alerta de alta forte (com "por quê" e notícia) quando alguma sobe bem mais que o normal.
Tudo respeitando o anti-spam e os limites do config.yaml.

Como rodar (dentro da pasta do projeto):
    python src/main.py             -> verifica quedas/altas e envia os alertas
    python src/main.py --teste     -> envia uma mensagem com os preços atuais (ignora as regras)
    python src/main.py --so-ver    -> só mostra na tela, não envia nada (combina com --teste)
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

import radar
import state
from alerts import (
    altas_detectadas,
    calcular_indicadores,
    movimentos_bruscos,
    pode_alertar,
    quedas_detectadas,
)
from explicacao import explicar
from mensagens import montar_alerta, montar_alerta_alta, montar_radar, montar_resumo
from prices import (
    buscar_historico_diario,
    buscar_maiores,
    buscar_medo_ganancia,
    buscar_mercado,
    buscar_precos_brl,
    buscar_velas_1h,
    buscar_velas_1min,
)
from telegram_bot import enviar_mensagem
from termometro import avaliar_curto_prazo, avaliar_longo_prazo

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


def calcular_termometro(config, moeda, dados, velas_1min, medo, agora):
    """Busca os dados extras e calcula o termômetro de compra da moeda.

    Só é chamado quando há um alerta de queda, para não gastar consultas à toa.
    Se algo falhar, devolve None e o alerta sai sem o termômetro.
    """
    perfil = moeda["perfil"]
    regras = config["termometro"][perfil]
    try:
        velas_1h = buscar_velas_1h(moeda["coinbase"])
        if perfil == "longo_prazo":
            diarios = buscar_historico_diario(moeda["id"])
            return avaliar_longo_prazo(regras, diarios, dados["current_price"], velas_1h, medo, agora)
        return avaliar_curto_prazo(regras, velas_1h, velas_1min, dados["current_price"], medo, agora)
    except Exception as erro:
        print(f"{moeda['simbolo']}: não consegui calcular o termômetro ({erro}).")
        return None


def rodar_radar(config, memoria, agora, indicadores_todos, velas_todas, enviar, so_ver):
    """Procura movimentos fortes nas outras moedas grandes e manda UMA mensagem com todos.

    Devolve a lista de moedas que passaram nos filtros (usada no resumo e no painel).
    """
    regras = config["radar"]
    principais = [m["simbolo"] for m in config["moedas"]]
    moedas = radar.filtrar(buscar_maiores(regras["quantas"]), regras, principais)
    print(f"Radar: {len(moedas)} moedas passaram nos filtros.")

    achados = radar.detectar(moedas, regras, memoria, agora)
    if not achados:
        print("Radar: nenhum movimento forte.")
        return moedas

    # "Por quê" e notícia só para as mais fortes (cada uma faz buscas de notícia).
    explicacoes = {}
    for achado in achados[: regras["max_detalhadas"]]:
        moeda = achado["moeda"]
        simbolo = moeda["symbol"].upper()
        principal = achado["regras"][0]
        try:
            explicacoes[simbolo] = explicar(
                {"simbolo": simbolo, "noticias": [moeda["name"], simbolo]},
                principal, achado["direcao"], achado["indicadores"][principal],
                config["moedas"], indicadores_todos, velas_todas,
            )
        except Exception as erro:
            print(f"Radar {simbolo}: não consegui montar o 'por quê' ({erro}).")

    enviar(montar_radar(achados, explicacoes, config["emojis"]))
    if not so_ver:
        for achado in achados:
            simbolo = achado["moeda"]["symbol"].upper()
            memoria[f"radar:{simbolo}:{achado['direcao']}"] = {
                "quando": agora, "preco": achado["moeda"]["current_price"],
            }
    return moedas


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

    # Período a rever em busca de movimentos bruscos: desde a última checagem,
    # mas sempre pelo menos os últimos 20 minutos (a Coinbase às vezes demora a
    # publicar os minutos mais recentes) e no máximo 2 horas para trás.
    desde = agora - timedelta(minutes=20)
    ultima_verificacao = state.carregar_ultima_verificacao()
    if ultima_verificacao is not None:
        desde = max(min(desde, ultima_verificacao), agora - timedelta(hours=2))

    # Índice de medo: buscado uma vez só, e apenas se algum termômetro precisar.
    medo_cache = {}

    def medo():
        if "valor" not in medo_cache:
            try:
                medo_cache["valor"] = buscar_medo_ganancia()
            except Exception as erro:
                print(f"Não consegui o índice de medo ({erro}).")
                medo_cache["valor"] = None
        return medo_cache["valor"]

    # 1º passo: junta os dados de TODAS as moedas (a explicação de uma moeda
    # compara com as outras no mesmo período).
    velas_todas = {}
    indicadores_todos = {}
    for moeda in config["moedas"]:
        simbolo = moeda["simbolo"]
        dados = mercado.get(moeda["id"])
        if not dados:
            print(f"{simbolo}: sem dados da CoinGecko agora, pulando.")
            continue

        # Movimentos bruscos (Coinbase). Se a Coinbase falhar, as outras regras continuam valendo.
        try:
            velas_todas[simbolo] = buscar_velas_1min(moeda["coinbase"])
            bruscos = movimentos_bruscos(velas_todas[simbolo], desde, agora)
        except Exception as erro:
            print(f"{simbolo}: não consegui o preço minuto a minuto ({erro}).")
            velas_todas[simbolo], bruscos = [], None

        indicadores_todos[simbolo] = calcular_indicadores(dados, bruscos)

    def porque(moeda, regras_disparadas, direcao, indicadores):
        """'Por que caiu/subiu?' para a regra principal do alerta (ou None se falhar)."""
        principal = regras_disparadas[0]
        inicio = fim = None
        if principal == "15min":
            prefixo = "brusca" if direcao == "queda" else "alta_brusca"
            inicio, fim = indicadores[f"{prefixo}_inicio"], indicadores[f"{prefixo}_fim"]
            variacao = indicadores["15min" if direcao == "queda" else "alta_15min"]
        elif principal == "distancia_maxima":
            variacao = indicadores["7d"]  # comparamos a semana inteira
        else:
            variacao = indicadores[principal]
        try:
            return explicar(moeda, principal, direcao, variacao, config["moedas"],
                            indicadores_todos, velas_todas, inicio, fim)
        except Exception as erro:
            print(f"{moeda['simbolo']}: não consegui montar o 'por quê' ({erro}).")
            return None

    # 2º passo: decide e envia os alertas de cada moeda.
    for moeda in config["moedas"]:
        simbolo = moeda["simbolo"]
        if simbolo not in indicadores_todos:
            continue
        dados = mercado[moeda["id"]]
        velas_1min = velas_todas[simbolo]
        indicadores = indicadores_todos[simbolo]
        preco = dados["current_price"]
        preco_brl = precos_brl.get(moeda["id"])

        # --- Quedas ---
        quedas = quedas_detectadas(indicadores, config["limites_queda"])
        if not quedas:
            print(f"{simbolo}: nenhuma queda além dos limites.")
        elif not pode_alertar(memoria.get(simbolo), preco, agora, config["anti_spam"], "15min" in quedas):
            print(f"{simbolo}: queda detectada ({', '.join(quedas)}), mas o anti-spam segurou.")
        else:
            termometro = calcular_termometro(config, moeda, dados, velas_1min, medo(), agora)
            explicacao = porque(moeda, quedas, "queda", indicadores)
            enviar(montar_alerta(moeda, dados, preco_brl, indicadores, quedas, termometro, explicacao,
                                 config["emojis"]))
            # Só anota na memória depois que a mensagem foi enviada com sucesso.
            if not so_ver:
                memoria[simbolo] = {"quando": agora, "preco": preco}

        # --- Altas fortes (memória separada da de quedas) ---
        chave_alta = f"{simbolo}:alta"
        altas = altas_detectadas(indicadores, config["limites_alta"])
        if not altas:
            print(f"{simbolo}: nenhuma alta além dos limites.")
        elif not pode_alertar(memoria.get(chave_alta), preco, agora, config["anti_spam"], "15min" in altas, alta=True):
            print(f"{simbolo}: alta detectada ({', '.join(altas)}), mas o anti-spam segurou.")
        else:
            explicacao = porque(moeda, altas, "alta", indicadores)
            enviar(montar_alerta_alta(moeda, dados, preco_brl, indicadores, altas, explicacao, config["emojis"]))
            if not so_ver:
                memoria[chave_alta] = {"quando": agora, "preco": preco}

    # --- Radar das outras moedas grandes (Fase 5) ---
    radar_moedas = []
    if config["radar"]["ativo"]:
        try:
            radar_moedas = rodar_radar(config, memoria, agora, indicadores_todos, velas_todas, enviar, so_ver)
        except Exception as erro:
            # O radar é um extra: se falhar, não pode atrapalhar os alertas principais.
            print(f"Radar: falhou ({erro}).")

    if not so_ver:
        state.salvar(memoria)
        state.salvar_ultima_verificacao(agora)


if __name__ == "__main__":
    main()
