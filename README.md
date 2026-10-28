# 🐋 WhaleRadar

Bot que avisa no Telegram quando BTC, ETH e SOL caem, explica em português simples por que caíram e indica se pode ser uma zona de compra.

**Só avisa, nunca opera.** Informação, não recomendação de investimento.

---

## Fase 0 — colocar para funcionar

### 1. Criar o bot no Telegram

1. No Telegram, procure **@BotFather** e mande `/newbot`.
2. Escolha um nome (ex.: `WhaleRadar`) e um usuário terminado em `bot` (ex.: `whaleradar_arthur_bot`).
3. O BotFather responde com um **token** (algo como `123456:ABC-xyz...`). Guarde — é a senha do bot. Não compartilhe.

### 2. Descobrir seu chat ID

1. Abra o seu bot no Telegram e mande qualquer mensagem (ex.: `oi`).
2. No navegador, abra (trocando `SEU_TOKEN` pelo token):
   `https://api.telegram.org/botSEU_TOKEN/getUpdates`
3. Procure `"chat":{"id":` — o número logo depois é o seu **chat ID**.

### 3. Testar no computador (opcional, precisa de Python)

1. Instale o Python 3.11+ em <https://www.python.org/downloads/> (marque **"Add python.exe to PATH"** na instalação).
2. Copie `.env.example` para `.env` e preencha o token e o chat ID.
3. No terminal, dentro da pasta do projeto:

   ```
   pip install -r requirements.txt
   python src/main.py --so-ver
   python src/main.py
   ```

   O primeiro comando só mostra a mensagem na tela; o segundo envia para o Telegram.

### 4. Colocar no GitHub

1. Crie um repositório **privado** chamado `whaleradar` e envie este código.
2. No repositório: **Settings → Secrets and variables → Actions → New repository secret**. Crie dois:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Aba **Actions → Radar → Run workflow** para rodar na hora.
4. Depois disso ele roda sozinho a cada 3 horas (na Fase 1 passa a ser a cada 15 min).

**Pronto quando:** a mensagem com os preços chega no celular, tanto rodando manualmente quanto pelo agendamento.

---

## Ajustes

Tudo que dá para mudar sem mexer no código está em [`config.yaml`](config.yaml).
