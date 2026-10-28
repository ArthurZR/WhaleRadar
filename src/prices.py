"""Busca de preços na CoinGecko (API pública, não precisa de conta)."""

import requests

URL_PRECO_SIMPLES = "https://api.coingecko.com/api/v3/simple/price"
URL_MERCADO = "https://api.coingecko.com/api/v3/coins/markets"


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
