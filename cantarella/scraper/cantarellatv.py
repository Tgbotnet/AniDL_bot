#@cantarellabots
"""
Compatibility facade - the old aniwatchtv.to scraper is gone.

``cantarella.telegram.*`` still imports ``cantarellatvDownloader`` from this
module, so the name stays, but every method now delegates to one of the two
supported sites:

  * ``https://animesalt.to``   - the default for this class (it occupies the
    bot's legacy "aniwatch" source slot)
  * ``https://anikototv.to``   - used automatically when the URL clearly
    belongs to it (e.g. an episode handed over from the anikoto slot)

Routing is by URL, because ``telegram/download.py`` has a single downloader
instance and hands it episode URLs produced by either scraper.
"""

from __future__ import annotations

from cantarella.scraper.anikoto import AnikotoScraper
from cantarella.scraper.animesalt import AnimeSaltScraper
from cantarella.scraper.reanime import ReAnimeScraper
from cantarella.scraper.base import detect_source

# this class represents the bot's "aniwatch" source slot
DEFAULT_SOURCE = "animesalt"


class cantarellatvDownloader:
    """Routes to animesalt.to (default), anikototv.to or reanime.to (URL-detected)."""

    def __init__(self, download_path="anime_downloads", progress_queue=None):
        self.download_path = download_path
        self.progress_queue = progress_queue
        self._scrapers = {
            "anikoto": AnikotoScraper(download_path, progress_queue),
            "animesalt": AnimeSaltScraper(download_path, progress_queue),
            "reanime": ReAnimeScraper(download_path, progress_queue),
        }

    # ── routing ──────────────────────────────────────────────────────────────

    def _pick(self, value=None):
        return self._scrapers[detect_source(value, DEFAULT_SOURCE)]

    # ── legacy surface ───────────────────────────────────────────────────────

    def list_episodes(self, value):
        return self._pick(value).list_episodes(value)

    def download_episode(self, url, quality="auto", name_override=None,
                         season_override=None, ep_num_override=None):
        return self._pick(url).download_episode(
            url, quality=quality, name_override=name_override,
            season_override=season_override, ep_num_override=ep_num_override,
        )

    def download_all_episodes(self, url, quality="auto"):
        return self._pick(url).download_all_episodes(url, quality=quality)

    def download_range(self, url, start, end, quality="auto"):
        return self._pick(url).download_range(url, start, end, quality=quality)

    def get_episode_info(self, url):
        return self._pick(url).get_episode_info(url)

    def get_anime_info(self, value):
        return self._pick(value).get_anime_info(value)

    def search_anime(self, query, limit=24):
        return self._pick(query).search_anime(query, limit=limit)
