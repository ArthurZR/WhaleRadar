"""Busca de dados de mercado em APIs públicas (sem conta): CoinGecko, Coinbase e alternative.me."""

import requests

URL_PRECO_SIMPLES = "https://api.coingecko.com/api/v3/simple/price"
URL_MERCADO = "https://api.coingecko.com/api/v3/coins/markets"
URL_VELAS_COINBASE = "https://api.exchange.coinbase.com/products/{produto}/candles"
URL_HISTORICO = "https://api.coingecko.com/api/v3/coins/{id_moeda}/market_chart"
URL_MEDO_GANANCIA = "https://api.alternative.me/fng/"


def buscar_mercado(ids_moedas):
    """Busca, em dólar, o preço atual, as variações e o histórico da semana.

    Retorna um dicionário por moeda, por exemplo:
        {"solana": {"current_price": 102.1,
                    "price_change_percentage_1h_in_currency": -0.4,
                    "price_change_percentage_24h_in_currency": 2.0,
                    "price_change_percentage_7d_in_currency": -3.8,
                    "sparkline_in_7d": {"price": [106.1, 105.8, ...]},  # preço de hora em hora
                    ...}}
    """
    parametros = {
        "vs_currency": "usd",
        "ids": ",".join(ids_moedas),
        "price_change_percentage": "1h,24h,7d",
        "sparkline": "true",
    }
    resposta = requests.get(URL_MERCADO, params=parametros, timeout=20)
    # Se a CoinGecko responder com erro (ex.: muitas consultas), paramos aqui com uma mensagem clara.
    resposta.raise_for_status()
    return {item["id"]: item for item in resposta.json()}


def buscar_precos_brl(ids_moedas):
    """Busca o preço atual de cada moeda em reais. Ex.: {"solana": 544.29}"""
    parametros = {"ids": ",".join(ids_moedas), "vs_currencies": "brl"}
    resposta = requests.get(URL_PRECO_SIMPLES, params=parametros, timeout=20)
    resposta.raise_for_status()
    return {id_moeda: dados["brl"] for id_moeda, dados in resposta.json().items()}


def buscar_velas(produto, segundos):
    """Busca na Coinbase (API pública) as últimas 300 "velas" de um produto.

    produto: nome na Coinbase, ex.: "SOL-USD".
    segundos: tamanho de cada vela (60 = 1 minuto, 3600 = 1 hora).
    Cada vela: [horário, mínima, máxima, abertura, fechamento, volume].
    Vem da mais recente para a mais antiga.
    """
    url = URL_VELAS_COINBASE.format(produto=produto)
    resposta = requests.get(
        url,
        params={"granularity": segundos},
        headers={"User-Agent": "whaleradar"},  # a Coinbase recusa pedidos sem identificação
        timeout=20,
    )
    resposta.raise_for_status()
    return resposta.json()


def buscar_velas_1min(produto):
    """Preço minuto a minuto das últimas ~5 horas."""
    return buscar_velas(produto, 60)


def buscar_velas_1h(produto):
    """Preço hora a hora dos últimos ~12 dias."""
    return buscar_velas(produto, 3600)


def buscar_historico_diario(id_moeda):
    """Preço de fechamento de cada dia do último ano (CoinGecko), do mais antigo ao mais recente."""
    parametros = {"vs_currency": "usd", "days": 365, "interval": "daily"}
    resposta = requests.get(URL_HISTORICO.format(id_moeda=id_moeda), params=parametros, timeout=20)
    resposta.raise_for_status()
    return [preco for _horario, preco in resposta.json()["prices"]]


def buscar_medo_ganancia():
    """Índice Fear & Greed (medo e ganância) de hoje, de 0 a 100.

    Perto de 0 = mercado com muito medo; perto de 100 = muita ganância (euforia).
    Retorna, por exemplo, {"valor": 23, "texto": "Extreme Fear"}.
    """
    resposta = requests.get(URL_MEDO_GANANCIA, params={"limit": 1}, timeout=20)
    resposta.raise_for_status()
    dados = resposta.json()["data"][0]
    return {"valor": int(dados["value"]), "texto": dados["value_classification"]}


def buscar_maiores(quantas):
    """As N maiores moedas por valor de mercado, com variações de 1h, 24h e 7 dias (CoinGecko)."""
    parametros = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": quantas,
        "page": 1,
        "price_change_percentage": "1h,24h,7d",
    }
    resposta = requests.get(URL_MERCADO, params=parametros, timeout=20)
    resposta.raise_for_status()
    return resposta.json()
