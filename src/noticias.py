"""Busca de notícias recentes no Google Notícias (RSS público, grátis, sem conta).

Só aceita manchetes que falam de movimento de preço na direção certa (queda ou
alta). Se nenhuma servir, devolve None: melhor dizer "não achei" do que mostrar
uma notícia qualquer.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

URL_GOOGLE_NOTICIAS = "https://news.google.com/rss/search"

# Pedaços de palavras que indicam movimento de preço (em minúsculas).
PALAVRAS = {
    "queda": [
        "cai ", "caem", "caiu", "queda", "despenc", "recua", "tomb", "derret", "desaba",
        "perde", "afunda", "liquidaç",
        " fall", " drop", "plunge", "slide", "crash", "tumble", "sell-off", "selloff", "sink", "slump",
    ],
    "alta": [
        "sobe", "sobem", "subiu", "alta", "dispara", "salta", "avança", "rali", "valoriz",
        "máxima", "recorde",
        " rise", "surge", "rally", "jump", "soar", "climb", "record high",
    ],
}

# Idiomas pesquisados, em ordem de preferência (português primeiro).
IDIOMAS = [
    {"hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"},
    {"hl": "en-US", "gl": "US", "ceid": "US:en"},
]


def _buscar_rss(termo, idioma):
    """Manchetes do último dia sobre o termo. Cada uma: {"titulo", "fonte", "link", "quando"}."""
    parametros = {"q": f"{termo} when:1d", **idioma}
    resposta = requests.get(
        URL_GOOGLE_NOTICIAS, params=parametros, headers={"User-Agent": "Mozilla/5.0"}, timeout=20
    )
    resposta.raise_for_status()

    manchetes = []
    for item in ET.fromstring(resposta.content).iter("item"):
        titulo_completo = item.findtext("title", "")
        # O Google escreve "Título da notícia - Nome do site".
        titulo, _, fonte = titulo_completo.rpartition(" - ")
        try:
            quando = parsedate_to_datetime(item.findtext("pubDate", ""))
        except (TypeError, ValueError):
            quando = None
        manchetes.append({
            "titulo": titulo or titulo_completo,
            "fonte": fonte,
            "link": item.findtext("link", ""),
            "quando": quando,
        })
    return manchetes


def buscar_noticia(termos, direcao):
    """Procura a manchete recente mais relacionada ao movimento.

    termos: lista do que pesquisar, em ordem (ex.: ["Solana", "criptomoedas"]).
    direcao: "queda" ou "alta".
    Retorna {"titulo", "fonte", "link", "quando"} ou None se nada servir.
    """
    palavras = PALAVRAS[direcao]
    agora = datetime.now(timezone.utc)

    for termo in termos:
        for idioma in IDIOMAS:
            try:
                manchetes = _buscar_rss(termo, idioma)
            except Exception as erro:
                print(f"Não consegui buscar notícias de '{termo}' ({erro}).")
                continue

            # Só manchetes que falam do movimento; entre elas, a mais recente.
            boas = [m for m in manchetes if any(p in f" {m['titulo'].lower()} " for p in palavras)]
            boas.sort(key=lambda m: m["quando"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            for manchete in boas:
                # Ignora notícias com mais de 24 horas.
                if manchete["quando"] is None or (agora - manchete["quando"]).total_seconds() <= 24 * 3600:
                    return manchete
    return None
