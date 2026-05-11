"""
deduplication.py — deduplikace článků přes Supabase
Tabulka: processed_articles (id int8 PK auto, url text unique, created_at timestamptz)
"""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Supabase REST API endpoint pro tabulku
_TABLE = "processed_articles"


def _get_client() -> tuple[str, dict]:
    """Vrátí base URL a hlavičky pro Supabase REST API."""
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    supabase_key = os.environ["SUPABASE_KEY"]
    base_url = f"{supabase_url}/rest/v1/{_TABLE}"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    return base_url, headers


def filter_new_articles(articles: list[Any]) -> list[Any]:
    """
    Přijme seznam článků (objektů s atributem .url),
    vrátí pouze ty, jejichž URL ještě není v Supabase.
    Nové URL rovnou uloží do tabulky.
    Deduplikuje i uvnitř aktuální dávky.
    """
    if not articles:
        return []

    base_url, headers = _get_client()

    # Deduplikace uvnitř dávky — zachovej první výskyt
    seen_in_batch: set[str] = set()
    unique_articles = []
    for article in articles:
        if article.url not in seen_in_batch:
            seen_in_batch.add(article.url)
            unique_articles.append(article)

    urls = [a.url for a in unique_articles]
    logger.info("Kontroluji %d unikátních URL v Supabase", len(urls))

    # Načti existující URL z Supabase (dotaz s filtrací in)
    try:
        url_filter = ",".join(f'"{u}"' for u in urls)
        resp = httpx.get(
            base_url,
            headers=headers,
            params={"url": f"in.({url_filter})", "select": "url"},
            timeout=30,
        )
        resp.raise_for_status()
        existing = {row["url"] for row in resp.json()}
    except Exception as exc:
        logger.error("Chyba při čtení z Supabase: %s", exc)
        # Při chybě propustíme vše — radši duplicita než ztráta článků
        return unique_articles

    new_articles = [a for a in unique_articles if a.url not in existing]
    logger.info("%d nových článků (z %d celkem, %d již zpracováno)", len(new_articles), len(unique_articles), len(existing))

    if not new_articles:
        return []

    # Ulož nové URL do Supabase
    rows = [{"url": a.url} for a in new_articles]
    try:
        resp = httpx.post(base_url, headers=headers, json=rows, timeout=30)
        resp.raise_for_status()
        logger.info("Uloženo %d nových URL do Supabase", len(rows))
    except Exception as exc:
        logger.error("Chyba při zápisu do Supabase: %s", exc)
        # Pokračuj i přes chybu zápisu

    return new_articles
