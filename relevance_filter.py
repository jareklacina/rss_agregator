"""
relevance_filter.py — filtrování relevance článků pomocí Claude Haiku
"""

import logging
import time
from typing import Any

import anthropic

logger = logging.getLogger(__name__)


def _build_prompt(title: str, description: str, topics: list[str]) -> str:
    topics_formatted = "\n".join(f"{i+1}. {t}" for i, t in enumerate(topics))
    return (
        f"Rozhodni, zda je tento článek relevantní pro ALESPOŇ JEDEN z těchto okruhů:\n"
        f"{topics_formatted}\n\n"
        f"Titulek: {title}\n"
        f"Popis: {description}\n\n"
        f"Odpověz POUZE jedním slovem: ANO nebo NE"
    )


def filter_relevant(
    articles: list[Any],
    topics: list[str],
    model: str,
    rate_limit: float = 1.0,
) -> list[Any]:
    """
    Filtruje články pomocí Claude Haiku.
    Posílá jen titulek + popis (ne plný text) — šetří tokeny.
    rate_limit = max počet requestů za sekundu.
    """
    client = anthropic.Anthropic()
    min_interval = 1.0 / rate_limit
    relevant = []
    last_request_time = 0.0

    for i, article in enumerate(articles):
        # Rate limiting
        elapsed = time.time() - last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

        prompt = _build_prompt(article.title, article.description, topics)
        logger.debug("Filtruji [%d/%d]: %s", i + 1, len(articles), article.title[:60])

        try:
            last_request_time = time.time()
            message = client.messages.create(
                model=model,
                max_tokens=5,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = message.content[0].text.strip().upper()
            if "ANO" in answer:
                relevant.append(article)
                logger.info("RELEVANTNÍ: %s", article.title[:80])
            else:
                logger.debug("Nerelevantní: %s", article.title[:80])
        except Exception as exc:
            logger.error("Chyba při filtrování článku '%s': %s", article.title[:60], exc)
            # Při chybě článek přeskočíme

    logger.info("Filtrování: %d/%d článků je relevantních", len(relevant), len(articles))
    return relevant
