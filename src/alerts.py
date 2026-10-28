"""Regras de queda e anti-spam."""

from datetime import datetime, timezone

# Janela da queda brusca, em minutos.
JANELA_BRUSCA_MINUTOS = 15


def maior_queda_brusca(velas_1min, desde, agora):
    """Procura a maior queda dentro de 15 minutos que aconteceu entre "desde" e "agora".

    Revê minuto a minuto todo o período desde a última checagem, então uma queda
    rápida não escapa mesmo que o bot só olhe o mercado a cada 15 minutos (ou que o
    GitHub atrase uma execução).

    velas_1min: velas de 1 minuto da Coinbase (mais recente primeiro).
    Retorna {"queda": -2.4, "inicio": datetime, "fim": datetime} ou None sem dados.
    "inicio" é o minuto do pico e "fim" o minuto do fundo.
    """
    # Cada vela: [horário, mínima, máxima, abertura, fechamento, volume].
    # Usamos o fechamento de cada minuto, que é menos sujeito a "picos" isolados.
    velas = sorted(velas_1min)  # do mais antigo para o mais recente
    janela = JANELA_BRUSCA_MINUTOS * 60
    pior = None

    for i, (horario, _min, _max, _abre, fecha, _vol) in enumerate(velas):
        if horario < desde.timestamp() or horario > agora.timestamp():
            continue
        # Preço mais alto nos 15 minutos antes deste minuto (pode ser antes de "desde").
        anteriores = [v for v in velas[: i + 1] if v[0] >= horario - janela]
        pico = max(anteriores, key=lambda v: v[4])
        queda = (fecha - pico[4]) / pico[4] * 100
        if pior is None or queda < pior["queda"]:
            pior = {"queda": queda, "inicio": pico[0], "fim": horario}

    if pior is None:
        return None
    pior["inicio"] = datetime.fromtimestamp(pior["inicio"], timezone.utc)
    pior["fim"] = datetime.fromtimestamp(pior["fim"], timezone.utc)
    return pior


def calcular_indicadores(dados, queda_brusca):
    """Junta, para uma moeda, os números que as regras de queda usam.

    "15min" é a maior queda brusca (em até 15 minutos) desde a última checagem;
    "brusca_inicio" e "brusca_fim" dizem quando ela aconteceu.
    "distancia_maxima" é quanto o preço atual está abaixo do preço mais alto
    dos últimos 7 dias (ex.: -12 quer dizer 12% abaixo).
    """
    preco_atual = dados["current_price"]
    historico_7d = (dados.get("sparkline_in_7d") or {}).get("price") or []
    maxima_7d = max(historico_7d + [preco_atual])

    queda_brusca = queda_brusca or {}
    return {
        "15min": queda_brusca.get("queda"),
        "brusca_inicio": queda_brusca.get("inicio"),
        "brusca_fim": queda_brusca.get("fim"),
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
