"""
fetcher.py — stažení RSS feedů a routing autentizace podle zdroje
"""

import os
import logging
import feedparser
import httpx
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Article:
    """Reprezentuje jeden článek z RSS feedu."""
    title: str
    url: str
    description: str
    source_name: str
    auth_strategy: str
    author: str = ""
    full_text: str = ""


def _build_auth_headers(auth_strategy: str, auth_config: dict) -> dict:
    """Sestaví HTTP hlavičky podle autentizační strategie."""
    strategy_type = auth_config.get("type", "none")

    if strategy_type == "none":
        return {}

    if strategy_type == "cookie":
        env_var = auth_config.get("env_var", "")
        cookie_value = os.environ.get(env_var, "")
        if not cookie_value:
            logger.warning("Chybí env proměnná '%s' pro autentizaci '%s'", env_var, auth_strategy)
            return {}
        return {"Cookie": cookie_value}

    # Připraveno pro budoucí strategie: api_key, oauth, bearer_token
    logger.warning("Neznámá autentizační strategie: %s", strategy_type)
    return {}


def fetch_feeds(feeds_config: list[dict], auth_strategies: dict) -> list[Article]:
    """
    Stáhne všechny nakonfigurované RSS feedy a vrátí seznam článků.
    Každý článek nese informaci o zdroji a jeho autentizační strategii.
    """
    articles: list[Article] = []

    for feed_cfg in feeds_config:
        name = feed_cfg["name"]
        url = feed_cfg["url"]
        auth_key = feed_cfg.get("auth", "none")

        logger.info("Stahuji feed: %s (%s)", name, url)
        try:
            parsed = feedparser.parse(url)
        except Exception as exc:
            logger.error("Chyba při stahování feedu '%s': %s", name, exc)
            continue

        if parsed.bozo and parsed.bozo_exception:
            logger.warning("Feed '%s' má problémy s parsováním: %s", name, parsed.bozo_exception)

        count_before = len(articles)
        for entry in parsed.entries:
            title = getattr(entry, "title", "").strip()
            link = getattr(entry, "link", "").strip()
            # description může být v různých polích
            description = (
                getattr(entry, "summary", "")
                or getattr(entry, "description", "")
                or ""
            ).strip()
            author = getattr(entry, "author", "").strip()

            if not link:
                continue

            articles.append(Article(
                title=title,
                url=link,
                description=description,
                source_name=name,
                auth_strategy=auth_key,
                author=author,
            ))

        fetched = len(articles) - count_before
        logger.info("Feed '%s': %d článků", name, fetched)

    logger.info("Celkem staženo: %d článků ze %d feedů", len(articles), len(feeds_config))
    return articles


def get_article_headers(auth_strategy: str, auth_strategies_config: dict) -> dict:
    """
    Vrátí HTTP hlavičky pro stažení článku podle jeho autentizační strategie.
    Veřejné API pro article_reader.py.
    """
    auth_config = auth_strategies_config.get(auth_strategy, {"type": "none"})
    base_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    auth_headers = _build_auth_headers(auth_strategy, auth_config)
    return {**base_headers, **auth_headers}
