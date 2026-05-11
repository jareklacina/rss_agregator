"""
main.py — hlavní orchestrace RSS Digest Agent pipeline
"""

import logging
import sys
import yaml

from fetcher import fetch_feeds
from deduplication import filter_new_articles
from relevance_filter import filter_relevant
from article_reader import fetch_all_articles
from summarizer import summarize_articles
from telegram_sender import send_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run():
    logger.info("=== RSS Digest Agent — spuštění pipeline ===")

    cfg = load_config()
    feeds = cfg["feeds"]
    auth_strategies = cfg["auth_strategies"]
    topics = cfg["relevance_topics"]
    models = cfg["models"]
    limits = cfg["limits"]

    # --- Krok 2: Stažení RSS feedů ---
    articles = fetch_feeds(feeds, auth_strategies)
    if not articles:
        logger.info("Žádné články ke zpracování. Konec.")
        return

    # --- Krok 3: Deduplikace přes Supabase ---
    articles = filter_new_articles(articles)
    if not articles:
        logger.info("Všechny články již byly zpracovány. Konec.")
        return

    # --- Krok 4+5: Filtrování relevance pomocí Claude Haiku ---
    articles = filter_relevant(
        articles,
        topics=topics,
        model=models["filter"],
        rate_limit=limits["filter_rate_limit"],
    )
    if not articles:
        logger.info("Žádný článek nebyl vyhodnocen jako relevantní. Konec.")
        return

    # --- Krok 6+7: Stažení plného textu a extrakce ---
    articles = fetch_all_articles(
        articles,
        auth_strategies_config=auth_strategies,
        max_chars=limits["article_max_chars"],
    )
    if not articles:
        logger.info("Nepodařilo se stáhnout žádný článek. Konec.")
        return

    # --- Krok 8: Sumarizace pomocí Claude Sonnet ---
    articles = summarize_articles(
        articles,
        model=models["summarize"],
        rate_limit=limits["summarize_rate_limit"],
    )
    if not articles:
        logger.info("Nepodařilo se sumarizovat žádný článek. Konec.")
        return

    # --- Krok 9+10: Formátování a odeslání do Telegramu ---
    sent = send_all(articles, send_delay=limits["telegram_send_delay"])

    logger.info("=== Pipeline dokončena: %d zpráv odesláno ===", sent)


if __name__ == "__main__":
    run()
