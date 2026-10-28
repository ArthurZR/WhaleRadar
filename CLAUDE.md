# WhaleRadar

Bot de alertas de criptomoedas que avisa no Telegram quando BTC, ETH e SOL caem, explica em português simples por que caíram e indica se pode ser uma zona de compra.

## Princípios (valem para todo o código)

- **Só avisa, nunca opera.** Nenhuma compra ou venda automática. A decisão é sempre do usuário.
- **Não é consultoria financeira.** Toda mensagem de alerta inclui uma linha curta lembrando que é informação, não recomendação.
- **Linguagem simples.** Mensagens em português do Brasil, sem jargão. Se usar um termo técnico (RSI, funding), explicar em poucas palavras.
- **Honestidade sobre incerteza.** Se não houver explicação clara para uma queda, dizer isso. Nunca inventar causa.
- **Segredos fora do código.** Tokens e chaves só em variáveis de ambiente / GitHub Secrets. Nunca commitar `.env`.
- **Anti-spam.** Máximo de 1 alerta por moeda a cada poucas horas (configurável).

## Moedas iniciais

BTC, ETH, SOL. Preço em USD e em BRL.

## Stack

- Python 3.11+
- Dados de preço: API pública da CoinGecko (sem conta)
- Sentimento: índice Fear & Greed (alternative.me)
- Notificação: Telegram Bot API
- Agendamento: GitHub Actions (roda a cada ~15 min, sem depender do computador do usuário)
- Explicações (Fase 3): modelo de texto fixo + link do Google Notícias (RSS público), sem custo. **Não** usar a API da Anthropic (decisão do Arthur: tem que ser grátis)

Manter dependências mínimas. Configurações (limiares, moedas, intervalo anti-spam) em um único arquivo `config.yaml`.

## Estrutura planejada

```
whaleradar/
├── CLAUDE.md
├── README.md
├── config.yaml
├── requirements.txt
├── .env.example
├── .gitignore
├── src/
│   ├── main.py            # ponto de entrada
│   ├── prices.py          # busca de preços
│   ├── alerts.py          # regras de queda e anti-spam
│   ├── telegram_bot.py    # envio de mensagens
│   ├── mensagens.py       # monta o texto das mensagens (emojis, arte da baleia)
│   ├── termometro.py      # termômetro de compra 0 a 5 (longo e curto prazo)
│   ├── explicacao.py      # "por quê": compara com o mercado e dá nível de certeza
│   ├── noticias.py        # busca manchete recente no Google Notícias
│   ├── backtest.py        # testa as regras no passado (Fase 4)
│   └── state.py           # guarda último alerta de cada moeda (.estado/, no cache do Actions)
└── .github/workflows/
    └── radar.yml          # agendamento
```

## Roteiro por fases

- **Fase 0 – Fundação (feita):** repositório, bot do Telegram, chaves, workflow agendado, mensagem de teste chegando no celular.
- **Fase 1 – Detector de queda (feita em 28/10/2026):** alerta por queda em 15 min / 1h / 24h / 7d e distância da máxima de 7 dias, com anti-spam. Limites no perfil "frequente" (-2% 15 min, -3% 1h, -4% 24h, -10% 7d, -10% da máxima). A queda brusca usa velas de 1 minuto da Coinbase (API pública): a cada execução o bot revê todo o período desde a checagem anterior (guardada em `.estado/ultima_verificacao.txt`) e pega a pior queda dentro de 15 min, então nada escapa entre checagens. Ela fura o silêncio de 4h (mínimo 30 min + preço 2% abaixo do último alerta). Roda a cada 15 min, disparado no horário exato pelo **cron-job.org** (conta do Arthur, chama a API `workflow_dispatch` com um token fine-grained só com Actions: write no WhaleRadar; **o token vence em 27/11/2026**, renovar com "Regenerate token" e colar no cron-job.org). O cron do próprio GitHub ficou como reserva, 1x/hora no minuto 41; o repositório é **público** para ter minutos grátis ilimitados (decisão do Arthur, 28/10/2026). Commits usam o e-mail anônimo do GitHub, nunca o pessoal.
- **Fase 2 – Termômetro de compra (feita em 28/10/2026):** placar 0 a 5 em todo alerta de queda (`src/termometro.py`), com perfil por moeda no `config.yaml`. **BTC e ETH = longo_prazo** (comprar e segurar): média de 200 dias, ≥20% abaixo da máxima anual, medo ≤40, RSI diário <35, sem nova mínima há 6h. **SOL = curto_prazo** (comprar e vender): RSI 1h <30, ≥8% abaixo da média de 7 dias, medo ≤40, volume 3h ≥50% acima do normal, repique ≥1% do fundo de 2h. 3+ pontos = 🎯, senão ⚠️; o último critério de cada perfil é o "freio" (se falhar, a leitura avisa que ainda não parou de cair). Dados extras (histórico diário CoinGecko, velas de 1h Coinbase, Fear & Greed) só são buscados quando há alerta. Também há **alertas de alta forte** (🚀) para as 3 moedas, pedido do Arthur: +2% 15 min, +3% 1h, +6% 24h, +15% 7d, com memória de anti-spam separada (chave `SIMBOLO:alta`), sem termômetro.
- **Fase 3 – "Por que caiu?" (feita em 28/10/2026, grátis):** em alertas de queda e de alta, 🌍 compara o movimento com o Bitcoin (ou, para o BTC, com a média de ETH e SOL) no mesmo período: ≥60% do movimento = "mercado todo", ≤25% = "específico da moeda", meio-termo = misto. 📰 link para manchete do Google Notícias que cite a moeda (ou o mercado cripto) E fale do movimento, com no máximo 6h (movimentos de 15 min/1h) ou 24h (demais); senão diz "não achei". Nível de certeza: mercado todo = média, demais = baixa; +1 nível só com notícia de até 6h. Liquidações ficaram de fora (não há fonte grátis sem conta).
- **Fase 4 – Backtest (feita em 28/10/2026):** `src/backtest.py` + workflow manual "Backtest" (relatório na aba Summary da execução e artefato com CSV). Simula hora a hora com as regras do `config.yaml` (sem a regra de 15 min) e compara com "momento qualquer". Resultado de 28/10/2026 (2 anos): alertas de queda sozinhos não batem a referência, mas o **termômetro separa bem**: BTC 🎯 subiu em 62% dos casos após 90 dias (+15% típico) vs 44% da referência; ETH 🎯 57% (+12%) vs 42%; SOL 🎯 subiu em 67% após 3 dias (+2%) vs 49%. Placar 4+ no longo prazo é ainda melhor (BTC 67%/+15,7%, ETH 65%/+14,7% em 90 dias). Mesmo com 🎯, o preço ainda caiu tipicamente ~8% (BTC) e ~15% (ETH) em 30 dias e ~3% (SOL) em 3 dias. Volume: ~6 (BTC), ~14 (ETH), ~19 (SOL) alertas de queda/mês, a maioria por 24h e distância da máxima. Alertas de alta: BTC seguiu subindo em 63% (7 dias); ETH e SOL ~50% (sem tendência). **Ajustes aplicados (aprovados pelo Arthur):** longo prazo exige 4 pontos para 🎯; com 🎯 a mensagem diz quanto o preço ainda costumou cair (📉, "é uma zona, não o fundo exato"); alertas de alta dizem o que costumou acontecer depois. Esses números ficam no bloco `historico` de cada moeda e o relatório do backtest traz os valores prontos para copiar. Nunca escrever conselho de compra ("compre aos poucos" etc.), só fatos do histórico.
- **Fase 5 – Radar de outras moedas:** varrer as ~50 maiores com filtros de liquidez e segurança.
- **Fase 6 – Extras:** resumo diário, alertas de alta, painel visual.

## Checklist da Fase 0

1. [x] Criar o bot no Telegram com o @BotFather e guardar o token
2. [x] Descobrir o chat ID do usuário (mandar mensagem ao bot e consultar `getUpdates`)
3. [x] Criar o repositório `whaleradar` no GitHub
4. [x] Adicionar `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` em GitHub Secrets
5. [x] Criar a estrutura de pastas e arquivos acima
6. [x] Implementar `prices.py` (preço BTC/ETH/SOL em USD e BRL via CoinGecko)
7. [x] Implementar `telegram_bot.py` (enviar mensagem de texto)
8. [x] `main.py` envia uma mensagem de teste com os preços atuais
9. [x] Criar `.github/workflows/radar.yml` com agendamento (cron) e execução manual
10. [~] Confirmar que a mensagem chega no Telegram, tanto local quanto pelo GitHub Actions (Actions manual: ok em 28/10/2026; falta: execução agendada e teste local, que precisa do Python instalado)

**Critério de pronto da Fase 0:** o GitHub Actions roda sozinho e o Telegram recebe uma mensagem com os preços de BTC, ETH e SOL.

## Identidade visual das mensagens (pedido do Arthur)

- Emoji antes de cada moeda: BTC 🪙, ETH 🔷, SOL 🟣 (em `config.yaml`).
- Toda mensagem termina com o aviso e a arte ASCII da baleia em `<code>` (não `<pre>`: o Arthur não gostou do quadro com "copy") (em `src/mensagens.py`). Mensagens são enviadas com `parse_mode=HTML`: escapar texto dinâmico.
- 🌍 antes da explicação do motivo; 📰 antes do link da notícia.
- 🎯 quando a leitura indica possível zona de compra; ⚠️ quando não indica. 🚀 nos alertas de alta forte; ⚡ em movimentos bruscos. Continua sendo "leitura", nunca "recomendação".

## Formato-alvo da mensagem (a partir da Fase 2/3)

```
🔻 🟣 SOL caiu 11% em 6h (R$ 1.020)
🌍 Por quê: o Bitcoin caiu 5% no mesmo período e houve muita venda forçada. Não achei notícia específica da Solana, então parece movimento do mercado todo.
Termômetro de compra: 3/5
✅ preço bem abaixo da média do último mês
✅ mercado com medo
❌ a queda ainda está acelerando
🎯 Leitura: possível zona de interesse, mas ainda sem sinal de que parou de cair.
ℹ️ Informação, não recomendação de investimento.
(arte da baleia)
```

## Decisões em aberto (perguntar ao usuário antes da fase indicada)

- ~~**Fase 3:** API da Anthropic ou texto fixo?~~ → decidido: grátis (texto fixo + link de notícia) (28/10/2026).
- ~~**Fase 2:** perfil do usuário~~ → decidido: BTC comprar e segurar; ETH segurar e comprar mais em quedas (mesmo termômetro do BTC); SOL comprar e vender (28/10/2026).
- ~~**Fase 1:** sensibilidade dos alertas~~ → decidido: **mais frequentes** (28/10/2026).

## Convenções de trabalho

- Código simples e comentado em português, pensado para quem está aprendendo.
- Cada fase termina com algo que roda e pode ser testado.
- Antes de mudar critérios de alerta, explicar o efeito em linguagem simples.
- Commits pequenos, com mensagem descritiva.

## Sobre o usuário

Arthur, designer gráfico e diretor criativo. Não precisa de jargão de programação. O painel visual (Fase 6) deve ter cuidado de design.
