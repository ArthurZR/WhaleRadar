"""Regras de queda, de alta forte e anti-spam."""

from datetime import datetime, timezone

# Janela dos movimentos bruscos, em minutos.
JANELA_BRUSCA_MINUTOS = 15


def movimentos_bruscos(velas_1min, desde, agora):
    """Procura a maior queda e a maior alta dentro de 15 minutos entre "desde" e "agora".

    Revê minuto a minuto todo o período desde a última checagem, então um
    movimento rápido não escapa mesmo que o bot só olhe o mercado a cada 15
    minutos (ou que uma execução atrase).

    velas_1min: velas de 1 minuto da Coinbase (mais recente primeiro).
    Retorna {"queda": {...} ou None, "alta": {...} ou None}, onde cada um é
    {"variacao": -2.4, "inicio": datetime, "fim": datetime}.
    """
    # Cada vela: [horário, mínima, máxima, abertura, fechamento, volume].
    # Usamos o fechamento de cada minuto, que é menos sujeito a "picos" isolados.
    velas = sorted(velas_1min)  # do mais antigo para o mais recente
    janela = JANELA_BRUSCA_MINUTOS * 60
    pior_queda = None
    maior_alta = None

    for i, (horario, _min, _max, _abre, fecha, _vol) in enumerate(velas):
        if horario < desde.timestamp() or horario > agora.timestamp():
            continue
        # Os 15 minutos antes deste minuto (podem ser antes de "desde").
        anteriores = [v for v in velas[: i + 1] if v[0] >= horario - janela]

        pico = max(anteriores, key=lambda v: v[4])
        queda = (fecha - pico[4]) / pico[4] * 100
        if pior_queda is None or queda < pior_queda["variacao"]:
            pior_queda = {"variacao": queda, "inicio": pico[0], "fim": horario}

        fundo = min(anteriores, key=lambda v: v[4])
        alta = (fecha - fundo[4]) / fundo[4] * 100
        if maior_alta is None or alta > maior_alta["variacao"]:
            maior_alta = {"variacao": alta, "inicio": fundo[0], "fim": horario}

    for movimento in (pior_queda, maior_alta):
        if movimento:
            movimento["inicio"] = datetime.fromtimestamp(movimento["inicio"], timezone.utc)
            movimento["fim"] = datetime.fromtimestamp(movimento["fim"], timezone.utc)
    return {"queda": pior_queda, "alta": maior_alta}


def calcular_indicadores(dados, bruscos):
    """Junta, para uma moeda, os números que as regras usam.

    "15min" é a maior queda brusca e "alta_15min" a maior alta brusca (em até
    15 minutos) desde a última checagem; "brusca_*" e "alta_brusca_*" dizem
    quando aconteceram. "distancia_maxima" é quanto o preço atual está abaixo do
    preço mais alto dos últimos 7 dias (ex.: -12 quer dizer 12% abaixo).
    """
    preco_atual = dados["current_price"]
    historico_7d = (dados.get("sparkline_in_7d") or {}).get("price") or []
    maxima_7d = max(historico_7d + [preco_atual])
    queda = (bruscos or {}).get("queda") or {}
    alta = (bruscos or {}).get("alta") or {}

    return {
        "15min": queda.get("variacao"),
        "brusca_inicio": queda.get("inicio"),
        "brusca_fim": queda.get("fim"),
        "alta_15min": alta.get("variacao"),
        "alta_brusca_inicio": alta.get("inicio"),
        "alta_brusca_fim": alta.get("fim"),
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


def altas_detectadas(indicadores, limites):
    """Igual a quedas_detectadas, mas para altas fortes (limites positivos)."""
    passaram = []
    for nome, limite in limites.items():
        # A alta brusca fica guardada em "alta_15min" (o "15min" é a queda brusca).
        valor = indicadores.get("alta_15min" if nome == "15min" else nome)
        if valor is not None and valor >= limite:
            passaram.append((valor / limite, nome))
    passaram.sort(reverse=True)
    return [nome for _forca, nome in passaram]


def pode_alertar(ultimo_alerta, preco_atual, agora, regras, brusca=False, alta=False):
    """Anti-spam: decide se esta moeda pode avisar de novo agora.

    ultimo_alerta: {"quando": datetime, "preco": float} ou None se nunca avisou.
    brusca: True se um dos movimentos é o brusco de 15 minutos.
    alta: True para avisos de alta (aí o preço precisa ter SUBIDO mais).
    """
    if ultimo_alerta is None:
        return True

    horas_passadas = (agora - ultimo_alerta["quando"]).total_seconds() / 3600

    # Faz tempo o bastante: esquece o alerta antigo.
    if horas_passadas >= regras["esquecer_apos_horas"]:
        return True

    # Ainda dentro do período de silêncio. Movimento brusco usa um silêncio bem menor.
    silencio_horas = regras["intervalo_brusca_minutos"] / 60 if brusca else regras["intervalo_horas"]
    if horas_passadas < silencio_horas:
        return False

    # Só avisa se o preço andou mais desde o último alerta (evita aviso repetido).
    movimento = regras["nova_queda_minima"] / 100
    if alta:
        return preco_atual >= ultimo_alerta["preco"] * (1 + movimento)
    return preco_atual <= ultimo_alerta["preco"] * (1 - movimento)
