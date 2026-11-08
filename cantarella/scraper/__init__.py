#@cantarellabots
"""
Cantarella scrapers.

Three sites are supported:

    anikoto.py    -> https://anikototv.to  (megaplay player)
    animesalt.py  -> https://animesalt.to  (megaplay player)
    reanime.py    -> https://reanime.to    (flixcloud embed + XOR playlists)

    base.py       shared download / mux / progress plumbing
    wasm.py       tiny WASM interpreter for the flixcloud embed player
    search.py     unified ``search_anime()`` entry point
    cantarellatv.py / animetsu.py
                  thin compatibility facades that keep the class names the rest
                  of the bot imports (``cantarellatvDownloader``,
                  ``AnimetsuScraper``) while delegating to the sites above
"""

from cantarella.scraper.anikoto import AnikotoClient, AnikotoScraper
from cantarella.scraper.animesalt import AnimeSaltClient, AnimeSaltScraper
from cantarella.scraper.reanime import ReAnimeClient, ReAnimeScraper
from cantarella.scraper.base import detect_source, get_binary_path
from cantarella.scraper.search import get_scraper, resolve_source, search_anime

__all__ = [
    "AnikotoClient",
    "AnikotoScraper",
    "AnimeSaltClient",
    "AnimeSaltScraper",
    "ReAnimeClient",
    "ReAnimeScraper",
    "detect_source",
    "get_binary_path",
    "get_scraper",
    "resolve_source",
    "search_anime",
]
