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
NOMES_PERIODO = {"15min": "maior queda em 15 min", "1h": "1h", "24h": "24h", "7d": "7 dias"}


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


def _minutos(inicio, fim):
    """Duração de um movimento brusco, em minutos (no mínimo 1)."""
    return max(1, round((fim - inicio).total_seconds() / 60))


def _quando(inicio, fim):
    """O movimento brusco pode ter acontecido alguns minutos antes desta checagem."""
    inicio = inicio.astimezone(FUSO_BRASILIA).strftime("%H:%M")
    fim = fim.astimezone(FUSO_BRASILIA).strftime("%H:%M")
    return f"Aconteceu entre {inicio} e {fim} (horário de Brasília)"


def _linha_preco(dados, preco_brl):
    texto = f"Preço agora: US$ {formatar_numero(dados['current_price'])}"
    if preco_brl is not None:
        texto += f" | R$ {formatar_numero(preco_brl)}"
    return texto


def _painel(indicadores, destacados, alta):
    """Lista de variações; as que dispararam o alerta vão em negrito."""
    linhas = []
    for periodo, nome_periodo in NOMES_PERIODO.items():
        valor = indicadores[periodo]
        if periodo == "15min" and alta:
            valor, nome_periodo = indicadores["alta_15min"], "maior alta em 15 min"
        if valor is None:
            continue
        linha = f"• {nome_periodo}: {formatar_variacao(valor)}"
        linhas.append(f"<b>{linha}</b>" if periodo in destacados else linha)

    if not alta:
        distancia = indicadores["distancia_maxima"]
        linha = (
            f"• {formatar_numero(abs(distancia), 1)}% abaixo da máxima de 7 dias"
            f" (US$ {formatar_numero(indicadores['maxima_7d'])})"
        )
        linhas.append(f"<b>{linha}</b>" if "distancia_maxima" in destacados else linha)
    return linhas


def _bloco_termometro(termometro, emojis):
    """Placar do termômetro de compra, com cada ponto explicado."""
    linhas = [f"<b>Termômetro de compra: {termometro['pontos']}/{termometro['total']}</b>"]
    for ok, texto in termometro["itens"]:
        linhas.append(f"{'✅' if ok else '❌'} {escape(texto, quote=False)}")
    emoji = emojis["zona_interesse"] if termometro["interesse"] else emojis["sem_sinal"]
    linhas.append(f"{emoji} <b>Leitura:</b> {escape(termometro['leitura'], quote=False)}")
    return linhas


def montar_alerta(moeda, dados, preco_brl, indicadores, quedas, termometro, emojis):
    """Mensagem de alerta de queda para uma moeda.

    quedas: regras que dispararam, a mais forte primeiro (ex.: ["24h", "1h"]).
    termometro: resultado do termometro.py, ou None se não deu para calcular.
    """
    nome = f"{moeda['emoji']} {moeda['simbolo']}"

    # Título: descreve a queda mais forte.
    principal = quedas[0]
    if principal == "distancia_maxima":
        queda = formatar_numero(abs(indicadores["distancia_maxima"]), 1)
        titulo = f"🔻 {nome} está {queda}% abaixo da máxima dos últimos 7 dias"
    elif principal == "15min":
        queda = formatar_numero(abs(indicadores["15min"]), 1)
        minutos = _minutos(indicadores["brusca_inicio"], indicadores["brusca_fim"])
        titulo = f"⚡ {nome} despencou {queda}% em {minutos} min"
    else:
        queda = formatar_numero(abs(indicadores[principal]), 1)
        titulo = f"🔻 {nome} caiu {queda}% em {NOMES_PERIODO[principal]}"

    linhas = [f"<b>{titulo}</b>"]
    if "15min" in quedas:
        linhas.append(_quando(indicadores["brusca_inicio"], indicadores["brusca_fim"]))
    linhas += [_linha_preco(dados, preco_brl), "", "Variação:", *_painel(indicadores, quedas, alta=False)]

    linhas.append("")
    if termometro:
        linhas += _bloco_termometro(termometro, emojis)
    else:
        linhas.append(f"{emojis['sem_sinal']} Termômetro de compra indisponível agora (falha ao buscar dados).")

    return finalizar("\n".join(linhas))


def montar_alerta_alta(moeda, dados, preco_brl, indicadores, altas):
    """Mensagem de alerta de alta forte (sem termômetro de compra).

    altas: regras que dispararam, a mais forte primeiro (ex.: ["24h", "1h"]).
    """
    nome = f"{moeda['emoji']} {moeda['simbolo']}"

    principal = altas[0]
    if principal == "15min":
        alta = formatar_numero(indicadores["alta_15min"], 1)
        minutos = _minutos(indicadores["alta_brusca_inicio"], indicadores["alta_brusca_fim"])
        titulo = f"⚡🚀 {nome} disparou {alta}% em {minutos} min"
    else:
        alta = formatar_numero(indicadores[principal], 1)
        titulo = f"🚀 {nome} subiu {alta}% em {NOMES_PERIODO[principal]}"

    linhas = [f"<b>{titulo}</b>"]
    if "15min" in altas:
        linhas.append(_quando(indicadores["alta_brusca_inicio"], indicadores["alta_brusca_fim"]))
    linhas += [
        _linha_preco(dados, preco_brl),
        "",
        "Variação:",
        *_painel(indicadores, altas, alta=True),
        "",
        "Alta bem mais forte que o normal. Movimentos assim às vezes devolvem parte do ganho logo depois.",
    ]
    return finalizar("\n".join(linhas))
