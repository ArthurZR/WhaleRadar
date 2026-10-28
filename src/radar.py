"""Radar das outras moedas grandes (Fase 5).

Olha as maiores moedas por valor de mercado, tira as que não interessam
(dólares digitais, ouro tokenizado, pouca liquidez...) e procura movimentos
bem fortes. Tudo vai numa mensagem só, para não lotar o Telegram.
"""

from alerts import altas_detectadas, pode_alertar, quedas_detectadas


def filtrar(maiores, regras, simbolos_principais):
    """Deixa só as moedas que fazem sentido acompanhar.

    Tira: suas moedas principais (já têm alerta próprio), a lista "excluir" do
    config, moedas com pouco volume e moedas com preço praticamente parado
    (sinal de que é um dólar digital ou algo atrelado a outro ativo).
    """
    excluir = set(regras["excluir"])
    principais = {s.lower() for s in simbolos_principais}
    boas = []
    for moeda in maiores:
        if moeda["id"] in excluir or moeda["symbol"].lower() in principais:
            continue
        if (moeda.get("total_volume") or 0) < regras["volume_minimo_usd"]:
            continue
        var_24h = moeda.get("price_change_percentage_24h_in_currency")
        var_7d = moeda.get("price_change_percentage_7d_in_currency")
        if var_24h is None or var_7d is None:
            continue
        if abs(var_24h) < 0.3 and abs(var_7d) < 1.5:
            continue  # preço quase parado: provavelmente atrelado ao dólar
        boas.append(moeda)
    return boas


def indicadores_da(moeda):
    """Os números que as regras usam, no mesmo formato das moedas principais."""
    return {
        "1h": moeda.get("price_change_percentage_1h_in_currency"),
        "24h": moeda.get("price_change_percentage_24h_in_currency"),
        "7d": moeda.get("price_change_percentage_7d_in_currency"),
    }


def detectar(moedas, regras, memoria, agora):
    """Procura movimentos fortes que passam pelo anti-spam.

    Retorna uma lista de {"moeda", "direcao", "regras", "indicadores"},
    do movimento mais forte para o mais fraco.
    """
    achados = []
    for moeda in moedas:
        indicadores = indicadores_da(moeda)
        preco = moeda["current_price"]
        simbolo = moeda["symbol"].upper()
        for direcao, regras_disparadas in (
            ("queda", quedas_detectadas(indicadores, regras["limites_queda"])),
            ("alta", altas_detectadas(indicadores, regras["limites_alta"])),
        ):
            if not regras_disparadas:
                continue
            chave = f"radar:{simbolo}:{direcao}"
            if not pode_alertar(memoria.get(chave), preco, agora, regras["anti_spam"], alta=direcao == "alta"):
                print(f"Radar {simbolo}: {direcao} detectada, mas o anti-spam segurou.")
                continue
            principal = regras_disparadas[0]
            limite = regras["limites_queda" if direcao == "queda" else "limites_alta"][principal]
            achados.append({
                "moeda": moeda,
                "direcao": direcao,
                "regras": regras_disparadas,
                "indicadores": indicadores,
                "forca": indicadores[principal] / limite,
            })
    achados.sort(key=lambda a: a["forca"], reverse=True)
    return achados


def maiores_movimentos(moedas, quantas=3):
    """As que mais caíram e mais subiram em 24h (para o resumo diário e o painel)."""
    ordenadas = sorted(moedas, key=lambda m: m.get("price_change_percentage_24h_in_currency") or 0)

    def resumir(m):
        return {
            "simbolo": m["symbol"].upper(),
            "nome": m["name"],
            "posicao": m.get("market_cap_rank"),
            "preco": m["current_price"],
            "var_24h": m.get("price_change_percentage_24h_in_currency"),
        }

    return {
        "quedas": [resumir(m) for m in ordenadas[:quantas]],
        "altas": [resumir(m) for m in reversed(ordenadas[-quantas:])],
    }
