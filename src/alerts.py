"""Regras de queda e anti-spam."""


def calcular_indicadores(dados):
    """Junta, para uma moeda, os números que as regras de queda usam.

    "distancia_maxima" é quanto o preço atual está abaixo do preço mais alto
    dos últimos 7 dias (ex.: -12 quer dizer 12% abaixo).
    """
    preco_atual = dados["current_price"]
    historico_7d = (dados.get("sparkline_in_7d") or {}).get("price") or []
    maxima_7d = max(historico_7d + [preco_atual])

    return {
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


def pode_alertar(ultimo_alerta, preco_atual, agora, regras):
    """Anti-spam: decide se esta moeda pode avisar de novo agora.

    ultimo_alerta: {"quando": datetime, "preco": float} ou None se nunca avisou.
    """
    if ultimo_alerta is None:
        return True

    horas_passadas = (agora - ultimo_alerta["quando"]).total_seconds() / 3600

    # Ainda dentro do período de silêncio.
    if horas_passadas < regras["intervalo_horas"]:
        return False

    # Faz tempo o bastante: esquece o alerta antigo.
    if horas_passadas >= regras["esquecer_apos_horas"]:
        return True

    # No meio do caminho: só avisa se o preço caiu mais desde o último alerta.
    preco_limite = ultimo_alerta["preco"] * (1 - regras["nova_queda_minima"] / 100)
    return preco_atual <= preco_limite
