"""Backtest: testa as regras do WhaleRadar no passado.

Volta no tempo hora a hora (padrão: últimos 2 anos), aplica as MESMAS regras de
alerta, anti-spam e termômetro do config.yaml, e mede o que aconteceu com o
preço DEPOIS de cada alerta. Compara com um momento qualquer ("referência"),
para saber se os alertas realmente apontaram bons momentos.

Como rodar (no GitHub: aba Actions → Backtest → Run workflow):
    python src/backtest.py --anos 2

Gera:
    relatorio_backtest.md   -> relatório em português
    alertas_backtest.csv    -> cada alerta simulado (para análises futuras)

Limitações (ficam escritas no relatório):
- Usa preços de hora em hora: a regra de 15 minutos não dá para testar.
- O "repique" do perfil de curto prazo usa a mínima das últimas 2 horas
  (no bot de verdade é minuto a minuto).
"""

import argparse
import bisect
import csv
import statistics
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

from alerts import altas_detectadas, pode_alertar, quedas_detectadas
from mensagens import formatar_numero
from termometro import avaliar_curto_prazo, avaliar_longo_prazo

PASTA_PROJETO = Path(__file__).resolve().parent.parent
URL_VELAS = "https://api.exchange.coinbase.com/products/{produto}/candles"
URL_MEDO = "https://api.alternative.me/fng/"
HORA = 3600
DIA = 24 * HORA

# Prazos medidos depois de cada alerta, por perfil: (nome, horas).
PRAZOS = {
    "longo_prazo": [("30 dias", 30 * 24), ("90 dias", 90 * 24)],
    "curto_prazo": [("24h", 24), ("3 dias", 72)],
}
# Até onde procurar "quanto ainda caiu depois do alerta", por perfil (em horas).
JANELA_QUEDA_EXTRA = {"longo_prazo": 30 * 24, "curto_prazo": 72}


# ---------------------------------------------------------------- dados

def baixar_velas(produto, segundos, inicio, fim):
    """Velas da Coinbase entre inicio e fim (blocos de 300), da mais antiga para a mais recente."""
    velas = {}
    passo = timedelta(seconds=segundos * 300)
    atual = inicio
    while atual < fim:
        ate = min(atual + passo, fim)
        params = {
            "granularity": segundos,
            "start": atual.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": ate.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        for tentativa in range(5):
            resposta = requests.get(URL_VELAS.format(produto=produto), params=params,
                                    headers={"User-Agent": "whaleradar"}, timeout=30)
            if resposta.status_code != 429:  # 429 = "calma, muitas consultas"
                break
            time.sleep(2 * (tentativa + 1))
        resposta.raise_for_status()
        for vela in resposta.json():
            velas[vela[0]] = vela
        atual = ate
        time.sleep(0.2)  # educação com a API pública
    return [velas[horario] for horario in sorted(velas)]


def baixar_medo():
    """Histórico do índice de medo e ganância: {data (AAAA-MM-DD): valor}."""
    resposta = requests.get(URL_MEDO, params={"limit": 0}, timeout=30)
    resposta.raise_for_status()
    return {
        datetime.fromtimestamp(int(item["timestamp"]), timezone.utc).date().isoformat(): int(item["value"])
        for item in resposta.json()["data"]
    }


# ---------------------------------------------------------------- simulação

def variacao(preco_antes, preco_depois):
    if not preco_antes or not preco_depois:
        return None
    return (preco_depois - preco_antes) / preco_antes * 100


def simular_moeda(moeda, config, medo_por_dia, inicio, fim):
    """Roda as regras hora a hora para uma moeda. Devolve (alertas, referência)."""
    perfil = moeda["perfil"]
    print(f"{moeda['simbolo']}: baixando histórico...")
    horas = baixar_velas(moeda["coinbase"], HORA, inicio - timedelta(hours=320), fim)
    dias = baixar_velas(moeda["coinbase"], DIA, inicio - timedelta(days=400), fim)
    fechamento = {vela[0]: vela[4] for vela in horas}
    inicio_dias = [vela[0] for vela in dias]
    print(f"{moeda['simbolo']}: {len(horas)} horas e {len(dias)} dias de histórico. Simulando...")

    memoria = {}
    alertas = []
    referencia = []  # o que aconteceu depois de CADA hora (comprar num momento qualquer)

    def futuro(horario, preco):
        """Variação depois de cada prazo e a maior queda extra no caminho."""
        resultado = {}
        for nome, horas_prazo in PRAZOS[perfil] + [("7 dias", 7 * 24)]:
            resultado[nome] = variacao(preco, fechamento.get(horario + horas_prazo * HORA))
        janela = JANELA_QUEDA_EXTRA[perfil]
        if horario + janela * HORA <= horas[-1][0]:
            seguintes = [fechamento[h] for h in range(horario + HORA, horario + janela * HORA + 1, HORA)
                         if h in fechamento]
            resultado["queda_extra"] = variacao(preco, min(seguintes)) if seguintes else None
        else:
            resultado["queda_extra"] = None
        return resultado

    for i, vela in enumerate(horas):
        horario, preco = vela[0], vela[4]
        if horario < inicio.timestamp():
            continue
        agora = datetime.fromtimestamp(horario + HORA, timezone.utc)  # a vela fecha 1h depois de abrir

        referencia.append(futuro(horario, preco))

        # Mesmos números que o bot calcula ao vivo (menos a regra de 15 minutos).
        ultimos_7d = [fechamento[h] for h in range(horario - 167 * HORA, horario + 1, HORA) if h in fechamento]
        maxima_7d = max(ultimos_7d)
        indicadores = {
            "15min": None,
            "alta_15min": None,
            "1h": variacao(fechamento.get(horario - HORA), preco),
            "24h": variacao(fechamento.get(horario - 24 * HORA), preco),
            "7d": variacao(fechamento.get(horario - 168 * HORA), preco),
            "maxima_7d": maxima_7d,
            "distancia_maxima": variacao(maxima_7d, preco),
        }
        medo = medo_por_dia.get(agora.date().isoformat())
        medo = {"valor": medo, "texto": ""} if medo is not None else None

        # --- quedas ---
        quedas = quedas_detectadas(indicadores, config["limites_queda"])
        if quedas and pode_alertar(memoria.get("queda"), preco, agora, config["anti_spam"]):
            memoria["queda"] = {"quando": agora, "preco": preco}
            regras = config["termometro"][perfil]
            velas_1h = horas[max(0, i - 299): i + 1]
            if perfil == "longo_prazo":
                # Dias completos antes de hoje + o preço de agora (igual ao histórico da CoinGecko).
                ate = bisect.bisect_left(inicio_dias, horario - horario % DIA)
                diarios = [d[4] for d in dias[max(0, ate - 364): ate]] + [preco]
                termometro = avaliar_longo_prazo(regras, diarios, preco, velas_1h, medo, agora)
            else:
                # Sem preço minuto a minuto no passado: usa as velas de 1h das últimas 2 horas.
                termometro = avaliar_curto_prazo(regras, velas_1h, horas[i - 1: i + 1], preco, medo, agora)
            alertas.append({
                "moeda": moeda["simbolo"], "tipo": "queda", "quando": agora, "preco": preco,
                "regra": quedas[0], "pontos": termometro["pontos"], "interesse": termometro["interesse"],
                **futuro(horario, preco),
            })

        # --- altas ---
        altas = altas_detectadas(indicadores, config["limites_alta"])
        if altas and pode_alertar(memoria.get("alta"), preco, agora, config["anti_spam"], alta=True):
            memoria["alta"] = {"quando": agora, "preco": preco}
            alertas.append({
                "moeda": moeda["simbolo"], "tipo": "alta", "quando": agora, "preco": preco,
                "regra": altas[0], "pontos": None, "interesse": None,
                **futuro(horario, preco),
            })

    return alertas, referencia


# ---------------------------------------------------------------- relatório

def resumo(resultados, prazo):
    """(quantos, % que subiram, variação típica) para um prazo."""
    valores = [r[prazo] for r in resultados if r.get(prazo) is not None]
    if not valores:
        return 0, None, None
    subiram = sum(1 for v in valores if v > 0) / len(valores) * 100
    return len(valores), subiram, statistics.median(valores)


def pct(valor, sinal=False):
    if valor is None:
        return "–"
    prefixo = "+" if sinal and valor > 0 else ""
    return f"{prefixo}{formatar_numero(valor, 1)}%"


def linha_tabela(nome, resultados, perfil):
    prazo_curto, prazo_longo = (nome_prazo for nome_prazo, _ in PRAZOS[perfil])
    n, subiu_1, tipico_1 = resumo(resultados, prazo_curto)
    _, subiu_2, tipico_2 = resumo(resultados, prazo_longo)
    extras = [r["queda_extra"] for r in resultados if r.get("queda_extra") is not None]
    queda_extra = statistics.median(extras) if extras else None
    return (f"| {nome} | {n} | {pct(subiu_1)} | {pct(tipico_1, True)} | {pct(subiu_2)} | "
            f"{pct(tipico_2, True)} | {pct(queda_extra)} |")


def gerar_relatorio(config, resultados, inicio, fim, anos):
    meses = (fim - inicio).days / 30.4
    linhas = [
        "# Backtest do WhaleRadar",
        "",
        f"Período: **{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}** ({anos} anos), hora a hora, "
        "com as regras atuais do `config.yaml`.",
        "",
        "Como ler:",
        "- **Subiu depois**: em quantos % dos casos o preço estava mais alto depois do prazo.",
        "- **Variação típica**: a mediana (o caso do meio), menos distorcida que a média.",
        "- **Ainda caiu (típico)**: quanto o preço ainda desceu, no pior momento, depois do alerta.",
        "- **Momento qualquer** é a referência: o resultado de comprar numa hora aleatória. "
        "Um bom alerta precisa ser melhor que ela.",
        "",
    ]

    for moeda in config["moedas"]:
        alertas, referencia = resultados[moeda["simbolo"]]
        perfil = moeda["perfil"]
        quedas = [a for a in alertas if a["tipo"] == "queda"]
        altas = [a for a in alertas if a["tipo"] == "alta"]
        prazo_curto, prazo_longo = (nome for nome, _ in PRAZOS[perfil])
        nome_perfil = "comprar e segurar" if perfil == "longo_prazo" else "comprar e vender"

        linhas += [
            f"## {moeda['emoji']} {moeda['simbolo']} ({nome_perfil})",
            "",
            f"- Alertas de queda: **{len(quedas)}** (~{formatar_numero(len(quedas) / meses, 1)} por mês)",
            f"- Alertas de alta: **{len(altas)}** (~{formatar_numero(len(altas) / meses, 1)} por mês)",
            "",
            "### Depois dos alertas de queda",
            "",
            f"| Grupo | Casos | Subiu depois de {prazo_curto} | Variação típica | "
            f"Subiu depois de {prazo_longo} | Variação típica | Ainda caiu (típico) |",
            "|---|---|---|---|---|---|---|",
            linha_tabela("Momento qualquer (referência)", referencia, perfil),
            linha_tabela("Todos os alertas de queda", quedas, perfil),
            linha_tabela("🎯 Termômetro com sinal", [a for a in quedas if a["interesse"]], perfil),
            linha_tabela("⚠️ Termômetro sem sinal", [a for a in quedas if not a["interesse"]], perfil),
        ]
        for pontos in range(6):
            grupo = [a for a in quedas if a["pontos"] == pontos]
            if grupo:
                linhas.append(linha_tabela(f"Placar {pontos}/5", grupo, perfil))

        # Qual regra mais disparou (ajuda a calibrar o volume de alertas).
        contagem = {}
        for alerta in quedas:
            contagem[alerta["regra"]] = contagem.get(alerta["regra"], 0) + 1
        regras_texto = ", ".join(f"{regra}: {qtd}" for regra, qtd in sorted(contagem.items(), key=lambda x: -x[1]))
        linhas += ["", f"Regra principal dos alertas de queda: {regras_texto or 'nenhum'}.", ""]

        # Altas: devolveram o ganho?
        n, subiu, tipico = resumo(altas, "7 dias")
        _, subiu_ref, tipico_ref = resumo(referencia, "7 dias")
        linhas += [
            "### Depois dos alertas de alta",
            "",
            f"- Em **{pct(subiu)}** dos {n} casos o preço estava mais alto 7 dias depois "
            f"(momento qualquer: {pct(subiu_ref)}). Variação típica: {pct(tipico, True)} "
            f"(momento qualquer: {pct(tipico_ref, True)}).",
            "",
        ]

    linhas += [
        "## Limitações",
        "",
        "- Usa preços de hora em hora: a regra de queda/alta de **15 minutos não foi testada**.",
        "- No perfil de curto prazo, o \"repique\" usa a mínima das últimas 2 horas "
        "(o bot de verdade olha minuto a minuto).",
        "- Passado não garante futuro: o teste mostra como as regras teriam se comportado, não como vão se comportar.",
    ]
    return "\n".join(linhas) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Backtest das regras do WhaleRadar")
    parser.add_argument("--anos", type=float, default=2, help="quantos anos para trás testar")
    args = parser.parse_args()

    with open(PASTA_PROJETO / "config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    fim = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    inicio = fim - timedelta(days=round(365 * args.anos))
    medo_por_dia = baixar_medo()

    resultados = {}
    for moeda in config["moedas"]:
        resultados[moeda["simbolo"]] = simular_moeda(moeda, config, medo_por_dia, inicio, fim)

    relatorio = gerar_relatorio(config, resultados, inicio, fim, args.anos)
    (PASTA_PROJETO / "relatorio_backtest.md").write_text(relatorio, encoding="utf-8")

    # Planilha com todos os alertas simulados.
    with open(PASTA_PROJETO / "alertas_backtest.csv", "w", newline="", encoding="utf-8") as f:
        colunas = ["moeda", "tipo", "quando", "preco", "regra", "pontos", "interesse",
                   "24h", "3 dias", "7 dias", "30 dias", "90 dias", "queda_extra"]
        escritor = csv.DictWriter(f, fieldnames=colunas, extrasaction="ignore")
        escritor.writeheader()
        for alertas, _referencia in resultados.values():
            for alerta in alertas:
                escritor.writerow({**alerta, "quando": alerta["quando"].isoformat()})

    print(relatorio)


if __name__ == "__main__":
    main()
