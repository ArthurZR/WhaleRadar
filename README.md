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
   python src/main.py --teste --so-ver
   python src/main.py --teste
   python src/main.py
   ```

   O primeiro só mostra a mensagem de preços na tela; o segundo a envia para o Telegram;
   o terceiro é o modo normal (só avisa se houver queda).

### 4. Colocar no GitHub

1. Crie um repositório **público** chamado `whaleradar` e envie este código. (Público tem minutos grátis ilimitados no GitHub Actions; os segredos continuam protegidos. Nunca envie o `.env`.)
2. No repositório: **Settings → Secrets and variables → Actions → New repository secret**. Crie dois:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Aba **Actions → Radar → Run workflow** para rodar na hora. Marque a caixinha
   **"Mandar mensagem de teste"** para receber os preços atuais mesmo sem queda.
4. Depois disso ele roda sozinho a cada 15 minutos e **só manda mensagem quando alguma moeda cai** além dos limites do `config.yaml` (inclusive quedas bruscas de 2% em 15 minutos, mesmo que aconteçam entre uma checagem e outra).

**Pronto quando:** a mensagem com os preços chega no celular, tanto rodando manualmente quanto pelo agendamento.

---

## Ajustes

Tudo que dá para mudar sem mexer no código está em [`config.yaml`](config.yaml).
