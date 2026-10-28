"""Termômetro de compra: placar de 0 a 5, com cada ponto explicado.

Há dois perfis (escolhidos por moeda no config.yaml):
- longo_prazo: comprar e segurar — olha se está barato em meses e anos.
- curto_prazo: comprar e vender — olha se a queda exagerou nas últimas horas.

Cada função devolve:
    {"pontos": 3, "total": 5, "interesse": True,
     "itens": [(True, "preço abaixo da média de 200 dias (US$ 85.000,00)"), ...],
     "leitura": "possível zona de compra para quem segura a longo prazo."}
"""

from mensagens import formatar_numero


def calcular_rsi(precos, periodo=14):
    """RSI (Índice de Força Relativa), de 0 a 100.

    Compara o tamanho das subidas com o das descidas recentes. Abaixo de 30
    quer dizer que o preço caiu rápido demais ("sobrevendido"); acima de 70,
    que subiu rápido demais. precos: do mais antigo para o mais recente.
    """
    if len(precos) <= periodo:
        return None
    variacoes = [depois - antes for antes, depois in zip(precos, precos[1:])]
    ganhos = [max(v, 0) for v in variacoes]
    perdas = [max(-v, 0) for v in variacoes]

    # Média inicial e depois suavização (método de Wilder, o padrão do RSI).
    media_ganho = sum(ganhos[:periodo]) / periodo
    media_perda = sum(perdas[:periodo]) / periodo
    for ganho, perda in zip(ganhos[periodo:], perdas[periodo:]):
        media_ganho = (media_ganho * (periodo - 1) + ganho) / periodo
        media_perda = (media_perda * (periodo - 1) + perda) / periodo

    if media_perda == 0:
        return 100.0
    return 100 - 100 / (1 + media_ganho / media_perda)


def _item_medo(medo, limite):
    """Critério comum aos dois perfis: o mercado está com medo?"""
    if medo is None:
        return (False, "índice de medo indisponível agora")
    valor = medo["valor"]
    if valor <= limite:
        return (True, f"mercado com medo (índice {valor} de 100)")
    return (False, f"mercado sem medo (índice {valor} de 100)")


def _resultado(itens, minimo, leitura_sim, leitura_nao, ultimo_criterio_freio):
    """Soma os pontos e escreve a leitura final."""
    pontos = sum(1 for ok, _texto in itens if ok)
    interesse = pontos >= minimo
    if interesse:
        leitura = leitura_sim
        if not itens[-1][0]:
            # O último critério de cada perfil é o "freio" (parou de cair / repique).
            leitura += f", mas {ultimo_criterio_freio}"
    else:
        leitura = leitura_nao
    return {"pontos": pontos, "total": len(itens), "interesse": interesse,
            "itens": itens, "leitura": leitura + "."}


def avaliar_longo_prazo(regras, precos_diarios, preco_atual, velas_1h, medo, agora):
    """Perfil comprar e segurar.

    precos_diarios: fechamento diário do último ano (mais antigo primeiro).
    velas_1h: velas de 1 hora da Coinbase (qualquer ordem).
    """
    itens = []

    # 1) Abaixo da média de 200 dias?
    dias = regras["dias_media"]
    media = sum(precos_diarios[-dias:]) / len(precos_diarios[-dias:])
    if preco_atual < media:
        itens.append((True, f"preço abaixo da média de {dias} dias (US$ {formatar_numero(media)})"))
    else:
        itens.append((False, f"preço acima da média de {dias} dias (US$ {formatar_numero(media)})"))

    # 2) Longe da máxima do último ano?
    maxima = max(precos_diarios + [preco_atual])
    distancia = (preco_atual - maxima) / maxima * 100
    texto = f"{formatar_numero(abs(distancia), 1)}% abaixo da máxima do último ano (US$ {formatar_numero(maxima)})"
    itens.append((distancia <= regras["queda_da_maxima_anual"], texto))

    # 3) Mercado com medo?
    itens.append(_item_medo(medo, regras["medo_maximo"]))

    # 4) RSI diário baixo?
    rsi = calcular_rsi(precos_diarios)
    if rsi is None:
        itens.append((False, "RSI diário indisponível"))
    elif rsi < regras["rsi_diario_maximo"]:
        itens.append((True, f"RSI diário em {rsi:.0f}: caiu rápido demais nos últimos dias"))
    else:
        itens.append((False, f"RSI diário em {rsi:.0f}: a queda ainda não é exagerada"))

    # 5) A queda perdeu força? (a mínima das últimas 24h ficou para trás)
    horas = regras["horas_sem_nova_minima"]
    ultimas_24h = [v for v in velas_1h if v[0] >= agora.timestamp() - 24 * 3600]
    if not ultimas_24h:
        itens.append((False, "sem dados para ver se a queda perdeu força"))
    else:
        vela_fundo = min(ultimas_24h, key=lambda v: v[1])  # v[1] = mínima da hora
        horas_desde_fundo = (agora.timestamp() - vela_fundo[0]) / 3600
        if horas_desde_fundo >= horas:
            itens.append((True, f"não fez nova mínima nas últimas {horas} horas: a queda perdeu força"))
        else:
            itens.append((False, "fez nova mínima há pouco: a queda ainda está acelerando"))

    return _resultado(
        itens,
        regras["pontos_para_interesse"],
        "possível zona de compra para quem segura a longo prazo",
        "ainda sem sinal claro de compra para o longo prazo",
        "ainda sem sinal de que parou de cair",
    )


def avaliar_curto_prazo(regras, velas_1h, velas_1min, preco_atual, medo, agora):
    """Perfil comprar e vender.

    velas_1h / velas_1min: velas da Coinbase (qualquer ordem).
    """
    itens = []
    horarias = sorted(velas_1h)  # do mais antigo para o mais recente
    fechamentos = [v[4] for v in horarias]

    # 1) RSI de 1 hora baixo?
    rsi = calcular_rsi(fechamentos)
    if rsi is None:
        itens.append((False, "RSI de 1 hora indisponível"))
    elif rsi < regras["rsi_1h_maximo"]:
        itens.append((True, f"RSI de 1 hora em {rsi:.0f}: caiu rápido demais nas últimas horas"))
    else:
        itens.append((False, f"RSI de 1 hora em {rsi:.0f}: a queda ainda não é exagerada"))

    # 2) Bem abaixo da média dos últimos 7 dias?
    ultimos_7d = fechamentos[-7 * 24:]
    media = sum(ultimos_7d) / len(ultimos_7d)
    distancia = (preco_atual - media) / media * 100
    if distancia < 0:
        texto = f"{formatar_numero(abs(distancia), 1)}% abaixo da média de 7 dias (US$ {formatar_numero(media)})"
    else:
        texto = f"acima da média de 7 dias (US$ {formatar_numero(media)})"
    itens.append((distancia <= regras["abaixo_media_7d"], texto))

    # 3) Mercado com medo?
    itens.append(_item_medo(medo, regras["medo_maximo"]))

    # 4) Volume em pânico? (últimas 3h comparadas com a média dos 7 dias anteriores)
    if len(horarias) < 3 + 24:
        itens.append((False, "sem dados de volume suficientes"))
    else:
        volume_3h = sum(v[5] for v in horarias[-3:])
        anteriores = horarias[-3 - 7 * 24:-3]
        normal_3h = sum(v[5] for v in anteriores) / len(anteriores) * 3
        acima = (volume_3h / normal_3h - 1) * 100 if normal_3h else 0
        if acima >= regras["volume_acima_normal"]:
            itens.append((True, f"volume {formatar_numero(acima, 0)}% acima do normal nas últimas 3h (venda em pânico)"))
        else:
            itens.append((False, "volume normal nas últimas 3h (sem sinal de pânico)"))

    # 5) Repique começou? (subiu desde o fundo das últimas 2 horas)
    ultimas_2h = [v for v in velas_1min if v[0] >= agora.timestamp() - 2 * 3600]
    if not ultimas_2h:
        itens.append((False, "sem dados para ver se já está voltando"))
    else:
        fundo = min(v[1] for v in ultimas_2h)
        repique = (preco_atual - fundo) / fundo * 100
        if repique >= regras["repique_minimo"]:
            itens.append((True, f"já subiu {formatar_numero(repique, 1)}% desde o fundo das últimas 2h"))
        else:
            itens.append((False, "ainda colado no fundo das últimas 2h"))

    return _resultado(
        itens,
        regras["pontos_para_interesse"],
        "possível ponto de entrada para uma operação curta",
        "ainda sem sinal de entrada para operação curta",
        "o preço ainda não começou a voltar",
    )
