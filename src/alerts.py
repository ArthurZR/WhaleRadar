"""Regras de queda e anti-spam."""

# Janela da queda brusca, em minutos.
JANELA_BRUSCA_MINUTOS = 15


def calcular_queda_brusca(velas_1min, agora):
    """Quanto o preço caiu do ponto mais alto dos últimos 15 minutos até agora (em %).

    velas_1min: velas de 1 minuto da Coinbase (mais recente primeiro).
    Retorna None se não houver dados suficientes.
    """
    inicio_janela = agora.timestamp() - JANELA_BRUSCA_MINUTOS * 60
    # Cada vela: [horário, mínima, máxima, abertura, fechamento, volume]
    recentes = [vela for vela in velas_1min if vela[0] >= inicio_janela]
    if not recentes:
        return None
    pico = max(vela[2] for vela in recentes)
    preco_agora = recentes[0][4]  # fechamento da vela mais recente
    return (preco_agora - pico) / pico * 100


def calcular_indicadores(dados, queda_15min):
    """Junta, para uma moeda, os números que as regras de queda usam.

    "15min" é a queda brusca (do pico dos últimos 15 minutos até agora).
    "distancia_maxima" é quanto o preço atual está abaixo do preço mais alto
    dos últimos 7 dias (ex.: -12 quer dizer 12% abaixo).
    """
    preco_atual = dados["current_price"]
    historico_7d = (dados.get("sparkline_in_7d") or {}).get("price") or []
    maxima_7d = max(historico_7d + [preco_atual])

    return {
        "15min": queda_15min,
        "1h": dados.get("price_change_percentage_1h_in_currency"),
        "24h": dados.get("price_change_percentage_24h_in_currency"),
        "7d": dados.get("price_change_percentage_7d_in_currency"),
        "maxima_7d": maxima_7d,
        "distancia_maxima": (preco_atual - maxima_7d) / maxima_7d * 100,
    }


def quedas_detectadas(indicadores, limites):
    """Diz quais limites de queda foram ultrapassados.

    Retorna uma lista de nomes (ex.: ["24h", "distancia_maxima"]), começando pela
    queda mais forte em relação ao seu limite. Lista vazia = nada a avisar.
    """
    passaram = []
    for nome, limite in limites.items():
        valor = indicadores.get(nome)
        if valor is not None and valor <= limite:
            # "força" = quantas vezes a queda passou do limite (ex.: -8% num limite de -4% = 2x)
            passaram.append((valor / limite, nome))
    passaram.sort(reverse=True)
    return [nome for _forca, nome in passaram]


def pode_alertar(ultimo_alerta, preco_atual, agora, regras, brusca=False):
    """Anti-spam: decide se esta moeda pode avisar de novo agora.

    ultimo_alerta: {"quando": datetime, "preco": float} ou None se nunca avisou.
    brusca: True se uma das quedas é a queda brusca de 15 minutos.
    """
    if ultimo_alerta is None:
        return True

    horas_passadas = (agora - ultimo_alerta["quando"]).total_seconds() / 3600

    # Faz tempo o bastante: esquece o alerta antigo.
    if horas_passadas >= regras["esquecer_apos_horas"]:
        return True

    # Ainda dentro do período de silêncio. Queda brusca usa um silêncio bem menor.
    silencio_horas = regras["intervalo_brusca_minutos"] / 60 if brusca else regras["intervalo_horas"]
    if horas_passadas < silencio_horas:
        return False

    # Só avisa se o preço caiu mais desde o último alerta (evita aviso repetido).
    preco_limite = ultimo_alerta["preco"] * (1 - regras["nova_queda_minima"] / 100)
    return preco_atual <= preco_limite
