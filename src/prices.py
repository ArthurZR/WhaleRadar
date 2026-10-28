"""Busca de preços na CoinGecko (API pública, não precisa de conta)."""

import requests

URL_COINGECKO = "https://api.coingecko.com/api/v3/simple/price"


def buscar_precos(ids_moedas, moedas_referencia):
    """Pergunta à CoinGecko o preço atual de cada moeda.

    Exemplo de retorno:
        {"bitcoin": {"usd": 68000.0, "brl": 375000.0, "usd_24h_change": -2.1}, ...}

    O campo "usd_24h_change" é a variação em % nas últimas 24 horas.
    """
    parametros = {
        "ids": ",".join(ids_moedas),
        "vs_currencies": ",".join(moedas_referencia),
        "include_24hr_change": "true",
    }
    resposta = requests.get(URL_COINGECKO, params=parametros, timeout=20)
    # Se a CoinGecko responder com erro (ex.: muitas consultas), paramos aqui com uma mensagem clara.
    resposta.raise_for_status()
    return resposta.json()
