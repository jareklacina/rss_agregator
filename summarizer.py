"""
summarizer.py — sumarizace článků pomocí Claude Sonnet
"""

import logging
import time
from typing import Any

import anthropic

logger = logging.getLogger(__name__)


def _build_prompt(title: str, author: str, text: str) -> str:
    author_line = f"Autor: {author}\n" if author else ""
    return (
        f"Titulek: {title}\n"
        f"{author_line}"
        f"Text článku:\n{text}\n\n"
        f"Shrň tento článek do 2-3 vět v češtině. "
        f"Buď maximálně stručný a konkrétní — uveď jen klíčová jména a fakta. "
        f"Žádné nadpisy, žádné formátování, jen plynulý text."
    )


def summarize_articles(
    articles: list[Any],
    model: str,
    rate_limit: float = 1.0,
) -> list[Any]:
    """
    Sumarizuje plné texty článků pomocí Claude Sonnet.
    Výsledek ukládá do article.summary.
    Vrátí jen články, kde sumarizace proběhla úspěšně.
    """
    client = anthropic.Anthropic()
    min_interval = 1.0 / rate_limit
    last_request_time = 0.0
    successful = []

    for i, article in enumerate(articles):
        # Rate limiting
        elapsed = time.time() - last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

        prompt = _build_prompt(article.title, article.author, article.full_text)
        logger.info("Sumarizuji [%d/%d]: %s", i + 1, len(articles), article.title[:60])

        try:
            last_request_time = time.time()
            message = client.messages.create(
                model=model,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            article.summary = message.content[0].text.strip()
            successful.append(article)
            logger.debug("Shrnutí: %s", article.summary[:100])
        except Exception as exc:
            logger.error("Chyba při sumarizaci '%s': %s", article.title[:60], exc)
            # Při chybě článek přeskočíme

    logger.info("Sumarizováno %d/%d článků", len(successful), len(articles))
    return successful
