#@cantarellabots
"""
Unified search entry point.

``cantarella.telegram.plugins.search`` calls ``search_anime(query, source=...)``
with the raw bot setting (``"animetsu"`` / ``"aniwatch"`` / ``"reanime"``), so the
legacy names are kept as aliases for the sites that actually exist now:

    animetsu -> anikototv.to
    aniwatch -> animesalt.to
    reanime  -> reanime.to

Result shape is unchanged: ``{'title', 'id', 'type', 'url'}`` - the ``id`` is
the series slug and is fed straight back into ``anime_<id>`` callbacks.

The bot's text handler decides URL-vs-query by looking for the *old* domains, so
a pasted anikoto/animesalt/reanime link lands here as a "query". That case is
detected and resolved to a single series result instead of being searched for.
"""

from __future__ import annotations

from cantarella.scraper.anikoto import AnikotoScraper
from cantarella.scraper.animesalt import AnimeSaltScraper
from cantarella.scraper.reanime import ReAnimeScraper
from cantarella.scraper.base import detect_source, is_url

SOURCE_ALIASES = {
    "animetsu": "anikoto",
    "anikoto": "anikoto",
    "anikototv": "anikoto",
    "anikototv.to": "anikoto",
    "aniwatch": "animesalt",
    "aniwatchtv": "animesalt",
    "aniwatchtv.to": "animesalt",
    "animesalt": "animesalt",
    "animesalt.to": "animesalt",
    "reanime": "reanime",
    "reanime.to": "reanime",
}

DEFAULT_SOURCE = "reanime"


def resolve_source(source: str = None) -> str:
    """Map a bot setting / user string onto a real scraper key."""
    return SOURCE_ALIASES.get((source or "").strip().lower(), DEFAULT_SOURCE)


def get_scraper(source: str = None, **kwargs):
    """Build the scraper for a source key (extra kwargs go to its constructor)."""
    key = resolve_source(source)
    if key == "animesalt":
        return AnimeSaltScraper(**kwargs)
    if key == "reanime":
        return ReAnimeScraper(**kwargs)
    return AnikotoScraper(**kwargs)


def search_anime(query: str, source: str = None) -> list:
    """Search the selected site. Never raises - returns [] on failure."""
    query = (query or "").strip()
    if not query:
        return []

    # a pasted link wins over the configured source
    if is_url(query):
        detected = detect_source(query)
        if detected:
            try:
                return get_scraper(detected).search_anime(query)
            except Exception as exc:
                print(f"url lookup failed ({query}): {exc}", flush=True)
                return []

    try:
        return get_scraper(source).search_anime(query)
    except Exception as exc:
        print(f"search failed on {resolve_source(source)}: {exc}", flush=True)
        return []
