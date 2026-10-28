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
- Explicações em linguagem natural (Fase 3): API da Anthropic

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
│   └── state.py           # guarda último alerta de cada moeda
└── .github/workflows/
    └── radar.yml          # agendamento
```

## Roteiro por fases

- **Fase 0 – Fundação (atual):** repositório, bot do Telegram, chaves, workflow agendado, mensagem de teste chegando no celular.
- **Fase 1 – Detector de queda:** alerta por queda em 1h / 24h / 7d e distância da máxima recente, com anti-spam.
- **Fase 2 – Termômetro de compra:** placar 0 a 5 (preço barato vs histórico, medo extremo, RSI), cada ponto explicado.
- **Fase 3 – "Por que caiu?":** notícias, movimento do BTC/mercado e liquidações resumidos em linguagem simples, com nível de certeza.
- **Fase 4 – Backtest:** testar as regras em dados históricos e ajustar critérios com números.
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

## Formato-alvo da mensagem (a partir da Fase 2/3)

```
🔻 SOL caiu 11% em 6h (R$ 1.020)
Por quê: o Bitcoin caiu 5% no mesmo período e houve muita venda forçada. Não achei notícia específica da Solana, então parece movimento do mercado todo.
Termômetro de compra: 3/5
✅ preço bem abaixo da média do último mês
✅ mercado com medo
⚠️ a queda ainda está acelerando
Leitura: possível zona de interesse, mas ainda sem sinal de que parou de cair.
ℹ️ Informação, não recomendação de investimento.
```

## Decisões em aberto (perguntar ao usuário antes da fase indicada)

- **Fase 3:** usar a API da Anthropic para escrever os "porquês"? (custo baixo, centavos por alerta) ou modelo de texto fixo?
- **Fase 2:** perfil do usuário: comprar e segurar a longo prazo, ou operar movimentos curtos? Muda os critérios do termômetro.
- **Fase 1:** sensibilidade dos alertas: poucos e fortes (ex.: -8% em 24h) ou mais frequentes (ex.: -4%)?

## Convenções de trabalho

- Código simples e comentado em português, pensado para quem está aprendendo.
- Cada fase termina com algo que roda e pode ser testado.
- Antes de mudar critérios de alerta, explicar o efeito em linguagem simples.
- Commits pequenos, com mensagem descritiva.

## Sobre o usuário

Arthur, designer gráfico e diretor criativo. Não precisa de jargão de programação. O painel visual (Fase 6) deve ter cuidado de design.
