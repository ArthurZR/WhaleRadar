"""'Por que caiu (ou subiu)?' — explicação em linguagem simples, de graça.

Compara o movimento da moeda com o resto do mercado no MESMO período:
- se o Bitcoin (ou, para o próprio Bitcoin, ETH e SOL) mexeu parecido, é
  provavelmente um movimento do mercado todo;
- se ficou parado, o movimento parece ser específico daquela moeda.
E procura uma notícia recente que fale do movimento.

Nunca afirma a causa: diz o que "parece" e dá um nível de certeza.
"""

from datetime import datetime, timedelta, timezone

from mensagens import formatar_variacao
from noticias import buscar_noticia

NIVEIS = ["baixa", "média", "alta"]

# Palavras que indicam que a manchete fala do mercado cripto como um todo.
NOMES_MERCADO = ["cripto", "criptomoeda", "criptomoedas", "criptoativos",
                 "crypto", "cryptocurrency", "cryptocurrencies"]

VERBOS = {
    "queda": {"um": "caiu", "varios": "caíram", "nome": "a queda"},
    "alta": {"um": "subiu", "varios": "subiram", "nome": "a alta"},
}


def maiuscula(texto):
    """Primeira letra maiúscula sem mexer no resto ('o Bitcoin' -> 'O Bitcoin')."""
    return texto[:1].upper() + texto[1:]


def variacao_no_periodo(simbolo, janela, indicadores_todos, velas_todas, inicio, fim):
    """Quanto uma moeda (de referência) se mexeu na mesma janela do alerta, em %."""
    indicadores = indicadores_todos.get(simbolo)
    if indicadores is None:
        return None
    if janela == "distancia_maxima":
        janela = "7d"  # a máxima é dos últimos 7 dias
    if janela != "15min":
        return indicadores.get(janela)

    # Movimento brusco: compara o preço nos mesmos minutos de início e fim.
    velas = sorted(velas_todas.get(simbolo) or [])

    def preco_em(momento):
        anteriores = [v for v in velas if v[0] <= momento.timestamp()]
        return anteriores[-1][4] if anteriores else None  # fechamento do minuto

    if inicio is None or fim is None:
        return None
    antes, depois = preco_em(inicio), preco_em(fim)
    if not antes or not depois:
        return None
    return (depois - antes) / antes * 100


def explicar(moeda, janela, direcao, variacao_moeda, moedas, indicadores_todos, velas_todas,
             inicio=None, fim=None):
    """Monta a explicação de um alerta.

    janela: regra principal que disparou ("15min", "1h", "24h", "7d", "distancia_maxima").
    direcao: "queda" ou "alta".
    variacao_moeda: quanto a moeda se mexeu nessa janela, em %.
    moedas: lista de moedas do config. inicio/fim: só para movimentos bruscos.

    Retorna {"texto": "...", "noticia": {...} ou None, "certeza": "média"}.
    """
    simbolo = moeda["simbolo"]
    verbo = VERBOS[direcao]

    # Com quem comparar: as altcoins com o Bitcoin; o Bitcoin com as outras.
    if simbolo == "BTC":
        outras = [m["simbolo"] for m in moedas if m["simbolo"] != "BTC"]
        variacoes = [variacao_no_periodo(s, janela, indicadores_todos, velas_todas, inicio, fim) for s in outras]
        variacoes = [v for v in variacoes if v is not None]
        referencia = sum(variacoes) / len(variacoes) if variacoes else None
        nome_ref, plural = " e ".join(outras), True
    else:
        referencia = variacao_no_periodo("BTC", janela, indicadores_todos, velas_todas, inicio, fim)
        nome_ref, plural = "o Bitcoin", False

    verbo_ref = verbo["varios"] if plural else verbo["um"]
    em_media = " em média" if plural else ""
    mercado_todo = False

    if referencia is None or not variacao_moeda:
        texto = "Não consegui comparar com o resto do mercado agora."
        certeza = 0
    else:
        # Quanto do movimento da moeda o mercado também fez (1 = igual; 0 = nada).
        proporcao = referencia / variacao_moeda
        if proporcao >= 0.6:
            mercado_todo = True
            texto = (f"{maiuscula(nome_ref)} também {verbo_ref} ({formatar_variacao(referencia)}{em_media}) "
                     f"no mesmo período: parece um movimento do mercado todo, não algo só de {simbolo}.")
            certeza = 1
        elif proporcao <= 0.25:
            if proporcao < 0 and abs(referencia) >= 1:
                # O mercado foi para o lado contrário (ex.: Bitcoin subiu enquanto a moeda caiu).
                mexeu = "foram na direção contrária" if plural else "foi na direção contrária"
            else:
                mexeu = "quase não se mexeram" if plural else "quase não se mexeu"
            texto = (f"{maiuscula(nome_ref)} {mexeu} ({formatar_variacao(referencia)}{em_media}) "
                     f"no mesmo período: {verbo['nome']} parece ser específica de {simbolo}.")
            certeza = 0
        else:
            texto = (f"{maiuscula(nome_ref)} também {verbo_ref}, mas menos ({formatar_variacao(referencia)}{em_media}): "
                     f"parte parece ser do mercado e parte específica de {simbolo}.")
            certeza = 0

    # Notícia: primeiro sobre a própria moeda; se for movimento geral, sobre o mercado.
    # A manchete precisa citar a moeda (ou o mercado cripto) para valer.
    buscas = [(moeda["noticias"][0], moeda["noticias"])]
    if mercado_todo:
        btc = next((m["noticias"] for m in moedas if m["simbolo"] == "BTC"), ["Bitcoin"])
        buscas.append(("criptomoedas" if simbolo == "BTC" else btc[0], btc + NOMES_MERCADO))
    # Movimento rápido pede notícia bem recente; movimento de dias aceita notícia de até 1 dia.
    max_horas = 6 if janela in ("15min", "1h") else 24
    noticia = buscar_noticia(buscas, direcao, max_horas)
    # Só uma notícia bem recente (até 6h) aumenta a certeza; uma mais antiga
    # aparece como referência, mas pode não ter relação com o movimento de agora.
    if noticia and noticia["quando"] and datetime.now(timezone.utc) - noticia["quando"] <= timedelta(hours=6):
        certeza = min(certeza + 1, len(NIVEIS) - 1)

    return {"texto": texto, "noticia": noticia, "certeza": NIVEIS[certeza]}
