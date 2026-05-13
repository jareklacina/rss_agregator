"""
telegram_sender.py — formátování zpráv a odesílání do Telegram kanálu
"""

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _escape_markdown(text: str) -> str:
    """
    Escapuje znaky, které mají v Telegram Markdown (ne MarkdownV2) speciální význam.
    V základním Markdown módu je třeba escapovat jen * _ ` [
    """
    # Escapujeme jen uvnitř textu sumarizace, ne v celé zprávě
    for char in ["_", "`", "["]:
        text = text.replace(char, f"\\{char}")
    return text


def format_message(article: Any) -> str:
    """
    Sestaví Telegram zprávu pro jeden článek.
    Formát:
        *Titulek*
        ✍️ Autor, Zdroj

        Shrnutí...

        [Číst článek](url)
    """
    title = article.title.replace("*", "\\*")
    author_line = ""
    if article.author:
        author_line = f"\n✍️ {article.author}, {article.source_name}"
    else:
        author_line = f"\n✍️ {article.source_name}"

    summary = _escape_markdown(article.summary)

    return (
        f"*{title}*"
        f"{author_line}\n\n"
        f"{summary}\n\n"
        f"[Číst článek]({article.url})"
    )


def send_message(text: str, token: str, chat_id: str) -> bool:
    """Odešle jednu zprávu do Telegram kanálu. Při 429 počká a zkusí znovu."""
    url = TELEGRAM_API.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    for attempt in range(3):
        try:
            resp = httpx.post(url, json=payload, timeout=30)
            if resp.status_code == 429:
                retry_after = resp.json().get("parameters", {}).get("retry_after", 30)
                logger.warning("Telegram rate limit, čekám %d sekund", retry_after)
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("Telegram API chyba %d: %s", exc.response.status_code, exc.response.text[:200])
            return False
        except Exception as exc:
            logger.error("Chyba při odesílání do Telegramu: %s", exc)
            return False
    logger.error("Telegram: vyčerpány pokusy o odeslání")
    return False


def send_all(articles: list[Any], send_delay: float = 1.5) -> int:
    """
    Odešle všechny články do Telegram kanálu.
    Vrátí počet úspěšně odeslaných zpráv.
    """
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    sent = 0
    for i, article in enumerate(articles):
        text = format_message(article)
        logger.info("Odesílám zprávu [%d/%d]: %s", i + 1, len(articles), article.title[:60])

        if send_message(text, token, chat_id):
            sent += 1
        else:
            logger.warning("Zpráva nebyla odeslána: %s", article.title[:60])

        # Pauza mezi zprávami (rate limiting Telegramu)
        if i < len(articles) - 1:
            time.sleep(send_delay)

    logger.info("Odesláno %d/%d zpráv do Telegramu", sent, len(articles))
    return sent
