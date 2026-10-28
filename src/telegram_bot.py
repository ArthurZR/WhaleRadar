"""Envio de mensagens para o Telegram."""

import requests


def enviar_mensagem(token, chat_id, texto):
    """Manda uma mensagem de texto para o seu chat no Telegram."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    dados = {
        "chat_id": chat_id,
        "text": texto,
        # Permite <b>negrito</b> e <pre>texto de largura fixa</pre> na mensagem.
        "parse_mode": "HTML",
        # Evita que links na mensagem virem "cartões" grandes no Telegram.
        "disable_web_page_preview": True,
    }
    resposta = requests.post(url, data=dados, timeout=20)
    if not resposta.ok:
        # O Telegram explica o erro no corpo da resposta (ex.: "chat not found").
        raise RuntimeError(f"Telegram recusou a mensagem: {resposta.text}")
