"""
article_reader.py — stažení plného textu článku a extrakce čistého textu z HTML
"""

import logging
import re
import html
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# HTML tagy, které se vždy odstraní i s obsahem
_REMOVE_TAGS = {"script", "style", "nav", "footer", "header", "aside", "figure",
                "figcaption", "iframe", "noscript", "form", "button", "svg"}


def _clean_text(raw: str) -> str:
    """Odstraní HTML entity, kontrolní znaky a zdvojené mezery."""
    # Dekóduj HTML entity (&amp; &#160; atd.)
    text = html.unescape(raw)
    # Odstraň kontrolní znaky (kromě \n a \t)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Normalizuj whitespace — více mezer/tabulátorů na jednu
    text = re.sub(r"[ \t]+", " ", text)
    # Více než 2 po sobě jdoucí newliny na 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(html_content: str, max_chars: int = 6000) -> str:
    """
    Extrahuje čistý text z HTML.
    Pokud existuje <article> tag, extrahuje přednostně z něj.
    Ořízne na max_chars znaků.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Odstraň nežádoucí tagy i s obsahem
    for tag in soup.find_all(_REMOVE_TAGS):
        tag.decompose()

    # Upřednostni <article> tag
    container = soup.find("article") or soup.find("main") or soup.body or soup

    raw_text = container.get_text(separator="\n")
    text = _clean_text(raw_text)

    if len(text) > max_chars:
        text = text[:max_chars]
        # Ořízni na konci celé věty, pokud možno
        last_period = text.rfind(".")
        if last_period > max_chars * 0.8:
            text = text[: last_period + 1]
        text += " [...]"

    return text


def fetch_article_text(article: Any, auth_strategies_config: dict, max_chars: int = 6000) -> bool:
    """
    Stáhne plný text článku a uloží ho do article.full_text.
    Vrátí True při úspěchu, False při chybě.
    """
    from fetcher import get_article_headers

    headers = get_article_headers(article.auth_strategy, auth_strategies_config)

    try:
        resp = httpx.get(article.url, headers=headers, timeout=30, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("HTTP chyba %d při stahování '%s'", exc.response.status_code, article.url)
        return False
    except Exception as exc:
        logger.error("Chyba při stahování '%s': %s", article.url, exc)
        return False

    article.full_text = extract_text(resp.text, max_chars=max_chars)
    logger.debug("Stažen text článku '%s': %d znaků", article.title[:60], len(article.full_text))
    return True


def fetch_all_articles(articles: list[Any], auth_strategies_config: dict, max_chars: int = 6000) -> list[Any]:
    """
    Stáhne plné texty všech článků.
    Vrátí jen ty, kde stažení proběhlo úspěšně.
    """
    successful = []
    for article in articles:
        logger.info("Stahuji článek: %s", article.title[:80])
        if fetch_article_text(article, auth_strategies_config, max_chars):
            successful.append(article)
        else:
            logger.warning("Přeskočen článek (nepodařilo se stáhnout): %s", article.url)

    logger.info("Staženo %d/%d článků", len(successful), len(articles))
    return successful
