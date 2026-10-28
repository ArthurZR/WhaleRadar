"""Monta o texto das mensagens que vão para o Telegram.

As mensagens usam o formato HTML do Telegram: <b>negrito</b> e <code>texto de
largura fixa</code> (necessário para a arte da baleia não sair torta).
"""

from datetime import datetime, timedelta, timezone
from html import escape

# Horário de Brasília (UTC-3), para mostrar a hora certa na mensagem.
FUSO_BRASILIA = timezone(timedelta(hours=-3))

AVISO = "ℹ️ Informação, não recomendação de investimento."

# Assinatura que vai no fim de toda mensagem.
ARTE_BALEIA = r"""
        .
       ":"
     ___:____     |"\/"|
   ,'        `.    \  /
   |  O        \___/  |
 ~^~^~^~^~^~^~^~^~^~^~^~^~
""".strip("\n")

# Como cada regra de queda aparece escrita.
NOMES_PERIODO = {"1h": "1h", "24h": "24h", "7d": "7 dias"}


def formatar_numero(valor, casas=2):
    """Formata no padrão brasileiro: 1234567.8 -> '1.234.567,80'."""
    texto = f"{valor:,.{casas}f}"  # vira '1,234,567.80'
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_variacao(valor):
    """-5.234 -> '-5,2%'   3.1 -> '+3,1%'"""
    sinal = "+" if valor > 0 else ""
    return f"{sinal}{formatar_numero(valor, 1)}%"


def finalizar(texto):
    """Acrescenta o aviso e a arte da baleia ao fim de qualquer mensagem."""
    # <code> deixa a arte em fonte de largura fixa (fica alinhada) sem o quadro
    # com botão "copy" que o Telegram coloca em volta de blocos <pre>.
    return f"{texto}\n\n{AVISO}\n<code>{escape(ARTE_BALEIA, quote=False)}</code>"


def montar_resumo(config, mercado, precos_brl):
    """Mensagem de teste: preço atual de todas as moedas."""
    agora = datetime.now(FUSO_BRASILIA).strftime("%d/%m/%Y %H:%M")
    linhas = [f"<b>🐋 WhaleRadar — preços agora</b> ({agora})", ""]

    for moeda in config["moedas"]:
        nome = f"{moeda['emoji']} {moeda['simbolo']}"
        dados = mercado.get(moeda["id"])
        if not dados:
            linhas.append(f"{nome}: preço indisponível no momento")
            continue

        texto = f"{nome}: US$ {formatar_numero(dados['current_price'])}"
        if moeda["id"] in precos_brl:
            texto += f" | R$ {formatar_numero(precos_brl[moeda['id']])}"
        variacao = dados.get("price_change_percentage_24h_in_currency")
        if variacao is not None:
            seta = "🔻" if variacao < 0 else "🔺"
            texto += f"  {seta} {formatar_variacao(variacao)} em 24h"
        linhas.append(texto)

    return finalizar("\n".join(linhas))


def montar_alerta(moeda, dados, preco_brl, indicadores, quedas):
    """Mensagem de alerta de queda para uma moeda.

    quedas: regras que dispararam, a mais forte primeiro (ex.: ["24h", "1h"]).
    """
    nome = f"{moeda['emoji']} {moeda['simbolo']}"

    # Título: descreve a queda mais forte.
    principal = quedas[0]
    if principal == "distancia_maxima":
        queda = formatar_numero(abs(indicadores["distancia_maxima"]), 1)
        titulo = f"🔻 {nome} está {queda}% abaixo da máxima dos últimos 7 dias"
    else:
        queda = formatar_numero(abs(indicadores[principal]), 1)
        titulo = f"🔻 {nome} caiu {queda}% em {NOMES_PERIODO[principal]}"

    preco = f"Preço agora: US$ {formatar_numero(dados['current_price'])}"
    if preco_brl is not None:
        preco += f" | R$ {formatar_numero(preco_brl)}"

    # Painel com todas as variações; as que dispararam o alerta vão em negrito.
    painel = []
    for periodo, nome_periodo in NOMES_PERIODO.items():
        valor = indicadores[periodo]
        if valor is None:
            continue
        linha = f"• {nome_periodo}: {formatar_variacao(valor)}"
        painel.append(f"<b>{linha}</b>" if periodo in quedas else linha)

    distancia = indicadores["distancia_maxima"]
    linha = (
        f"• {formatar_numero(abs(distancia), 1)}% abaixo da máxima de 7 dias"
        f" (US$ {formatar_numero(indicadores['maxima_7d'])})"
    )
    painel.append(f"<b>{linha}</b>" if "distancia_maxima" in quedas else linha)

    texto = "\n".join([f"<b>{titulo}</b>", preco, "", "Variação:", *painel])
    return finalizar(texto)
