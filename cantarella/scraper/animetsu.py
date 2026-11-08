#@cantarellabots
"""
Compatibility facade - the old animetsu.live scraper is gone.

``cantarella.telegram.*`` still imports ``AnimetsuScraper`` from this module
(``ongoing.py``, ``plugins/search.py``, ``plugins/callbacks/anime.py``), so the
name stays, but it now talks to ``https://anikototv.to`` - the site that took
over the bot's "animetsu" source slot.

Callers hand in either a bare anime id/slug or a full URL; both are accepted,
and a URL that clearly belongs to the other supported site is forwarded there.
"""

from __future__ import annotations

from cantarella.scraper.anikoto import AnikotoScraper
from cantarella.scraper.animesalt import AnimeSaltScraper
from cantarella.scraper.reanime import ReAnimeScraper
from cantarella.scraper.base import detect_source

DEFAULT_SOURCE = "anikoto"


class AnimetsuScraper:
    """Routes to anikototv.to (default), animesalt.to or reanime.to (URL-detected)."""

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

    def search_anime(self, query, limit=24):
        return self._pick(query).search_anime(query, limit=limit)

    def list_episodes(self, value):
        return self._pick(value).list_episodes(value)

    def get_anime_info(self, value):
        return self._pick(value).get_anime_info(value)

    def get_episode_servers(self, value, kind="sub"):
        return self._pick(value).get_episode_servers(value, kind)

    def get_schedule(self, date_str=None):
        return self._pick(None).get_schedule(date_str)

    def get_home_sections(self):
        return self._pick(None).get_home_sections()

    def fetch_recently_updated(self, page=1, per_page=20):
        return self._pick(None).fetch_recently_updated(page=page, per_page=per_page)

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
