#@cantarellabots
"""
reanime.to scraper.

Pipeline
--------
  /api/v1/search?q=           -> [{anime_id, title, ...}]
  /anime/{slug}               -> full metadata (anilist / mal / tmdb ids)
  /watch/{slug}?ep=N (SSR)    -> episodes[] (numbers + titles)
  /api/flix/{anilist}/{ep}    -> [{serverName, dataLink, dataType}] (flixcloud embed)
  https://flixcloud.cc/e/...  -> SSR: obfuscation_seed + w_payload + fragments
  /api/m3u8/{token}           -> {vid fragment, key fragment}
  WASM _s/_r + PBKDF2 + AES   -> https://fetch9.flixcloud.cc/_v7/.../master.m3u8?token=
  master + variant playlists  -> base64 + XOR(__pk)   (__pk = WASM _c())
  segments (.webp/.png)       -> AES-128-CBC(key.bin, IV+seq) -> plain .ts
  video + audio .ts + subs    -> N_m3u8DL-RE-free mux via cantarella.scraper.base.merge_tracks

The master/variant playlists and the segment key/IV derivation mirror what
the in-browser HLS.js loader does (it checks for ``#EXTM3U`` and XOR-decrypts
with ``window.__pk``). Everything is fetched with ``curl_cffi`` + chrome
impersonation, which is what the site's Cloudflare rules expect.
"""

from __future__ import annotations

import base64
import concurrent.futures
import hashlib
import re
import time
import urllib.parse
from pathlib import Path

from Crypto.Cipher import AES

from cantarella.scraper.base import (
    BaseScraper,
    build_basename,
    clean_text,
    collect_output,
    config_format,
    detect_source,
    http_get,
    is_url,
    make_session,
    merge_tracks,
    Reporter,
    season_of,
    slugify,
)
from cantarella.scraper.wasm import run_wasm_mix, run_wasm_pk

BASE = "https://reanime.to"
FLIX = "https://flixcloud.cc"

_SLUG_RE = re.compile(r"/(?:anime|watch)/([^/?#]+)")
_EP_RE = re.compile(r"[?&]ep=(\d+)")
_EPISODES_RE = re.compile(r"episodes:\[(.*?)\],currentEpisode", re.S)
_ANILIST_RE = re.compile(r'"anilist_id":\s*(\d+)')

# ──────────────────────────────────────────────────────────────────────────────
#  helpers shared with the flixcloud player page
# ──────────────────────────────────────────────────────────────────────────────


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _field_map(seed: str) -> dict:
    """Mirror ``nr()`` in the player bundle: triple SHA-256 field names."""
    enc = seed
    for i in range(3):
        enc = _sha256_hex(enc + str(i))
    alt = enc
    for i in range(3):
        alt = _sha256_hex(alt + str(i))
    return {
        "keyField": f"kf_{enc[8:16]}",
        "ivField": f"ivf_{enc[16:24]}",
        "containerName": f"cd_{enc[24:32]}",
        "arrayName": f"ad_{enc[32:40]}",
        "objectName": f"od_{enc[40:48]}",
        "tokenField": f"{enc[48:64]}_{enc[56:64]}",
        "keyFrag2Field": f"{alt[0:16]}_{alt[16:24]}",
    }


def _b64(value: str) -> bytes:
    padded = value.strip().replace("-", "+").replace("_", "/")
    padded += "=" * (-len(padded) % 4)
    return base64.b64decode(padded)


def _parse_playlist_key(text: str):
    """(key_uri, iv_int) from ``#EXT-X-KEY`` or (None, None)."""
    match = re.search(r'#EXT-X-KEY:[^\n]*URI="([^"]+)"[^\n]*IV=0x([0-9a-fA-F]+)', text)
    if not match:
        match2 = re.search(r'#EXT-X-KEY:[^\n]*URI="([^"]+)"', text)
        if match2:
            return match2.group(1), None
        return None, None
    return match.group(1), int(match.group(2), 16)


def _xor_playlist(body: str, pk: bytes) -> str:
    """Decode a fetch9 playlist: base64 + repeating XOR with ``__pk``."""
    raw = _b64(body.strip())
    plain = bytes(b ^ pk[i % len(pk)] for i, b in enumerate(raw))
    return plain.decode("utf-8", errors="ignore")


# ──────────────────────────────────────────────────────────────────────────────
#  client
# ──────────────────────────────────────────────────────────────────────────────


class ReAnimeClient:
    BASE = BASE
    impersonate = "chrome124"

    def __init__(self, impersonate: str = "chrome124", timeout: int = 40, proxy: str = None):
        self.impersonate = impersonate
        self.timeout = timeout
        self.proxy = proxy
        self.session = make_session(impersonate, proxy)

    # ── transport ────────────────────────────────────────────────────────────

    def get(self, url, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("impersonate", self.impersonate)
        return http_get(self.session, url, **kwargs)

    # ── URL helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def series_url(value: str) -> str:
        raw = (value or "").strip().strip("\"'")
        if not raw:
            return ""
        match = _SLUG_RE.search(raw)
        if match:
            return f"{BASE}/anime/{match.group(1)}"
        slug = raw.split("?")[0].rstrip("/").split("/")[-1]
        return f"{BASE}/anime/{slug}"

    @staticmethod
    def slug_of(value: str) -> str:
        match = _SLUG_RE.search(value or "")
        if match:
            return match.group(1)
        return (value or "").split("?")[0].rstrip("/").split("/")[-1]

    @staticmethod
    def episode_of(value: str, default: int = 1) -> int:
        match = _EP_RE.search(value or "")
        try:
            return int(match.group(1)) if match else default
        except ValueError:
            return default

    # ── reads ────────────────────────────────────────────────────────────────

    def search(self, query: str, limit: int = 24) -> list:
        resp = self.get(f"{BASE}/api/v1/search", params={"q": query, "limit": limit})
        resp.raise_for_status()
        payload = resp.json()
        out = []
        for item in payload.get("results") or []:
            title = item.get("title") or {}
            name = title.get("english") or title.get("romaji") or title.get("native") or ""
            out.append({
                "title": clean_text(name) or item.get("anime_id", ""),
                "jp": clean_text(title.get("native") or ""),
                "url": f"{BASE}/anime/{item.get('anime_id')}",
                "slug": item.get("anime_id"),
                "type": item.get("format") or "ANIME",
                "anilist_id": item.get("anilist_id"),
            })
            if len(out) >= limit:
                break
        return out

    def anime_details(self, slug: str) -> dict:
        slug = self.slug_of(slug) if "://" in (slug or "") else (slug or "").strip("/")
        resp = self.get(f"{BASE}/api/v1/anime/{urllib.parse.quote(slug)}")
        resp.raise_for_status()
        data = resp.json()
        title = data.get("title") or {}
        name = title.get("english") or title.get("romaji") or slug.replace("-", " ").title()
        return {
            "anime_id": data.get("anime_id") or slug,
            "anilist_id": data.get("anilist_id"),
            "mal_id": data.get("mal_id"),
            "themoviedb_id": data.get("themoviedb_id"),
            "external_seasons": data.get("external_seasons") or {},
            "title": clean_text(name),
            "format": data.get("format") or "ANIME",
            "subbed": data.get("subbed") or 0,
            "dubbed": data.get("dubbed") or 0,
            "cover": (data.get("cover_image") or {}).get("large") if isinstance(data.get("cover_image"), dict) else "",
            "raw": data,
        }

    def episodes(self, slug: str) -> list:
        slug = self.slug_of(slug) if "://" in (slug or "") else (slug or "").strip("/")
        resp = self.get(f"{BASE}/watch/{urllib.parse.quote(slug)}", params={"ep": 1})
        resp.raise_for_status()
        html = resp.text
        match = _EPISODES_RE.search(html)
        if not match:
            return []
        block = match.group(1)
        episodes = []
        for chunk in re.finditer(
            r'dubbed:(true|false)[^}]*?episodeId:"([^"]+)"[^}]*?episode_number:(\d+)'
            r'[^}]*?subbed:(true|false)[^}]*?title:"([^"]*)"',
            block,
        ):
            episodes.append({
                "num": int(chunk.group(3)),
                "ep_id": chunk.group(2),
                "sub": chunk.group(4) == "true",
                "dub": chunk.group(1) == "true",
                "title": clean_text(chunk.group(5)) or f"Episode {chunk.group(3)}",
            })
        episodes.sort(key=lambda e: e["num"])
        return episodes

    def servers(self, anilist_id=None, mal_id=None, ep: int = 1,
                tmdb_id=None, tmdb_season=1) -> list:
        params = {}
        if mal_id:
            params["mal"] = str(mal_id)
        if not anilist_id and tmdb_id:
            params["tmdb"] = str(tmdb_id)
            params["season"] = str(tmdb_season or 1)
        url = f"{BASE}/api/flix/{anilist_id or 0}/{ep}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        resp = self.get(url, headers={"Accept": "application/json"})
        resp.raise_for_status()
        payload = resp.json()
        servers = payload.get("servers") or []
        return [{
            "name": s.get("serverName", "?"),
            "type": s.get("dataType", "sub"),
            "server_id": s.get("$id", ""),
            "link_id": s.get("dataLink", ""),
        } for s in servers if s.get("dataLink")]

    def flix_sources(self, embed_url: str) -> dict:
        """Resolve a flixcloud embed to ``{master_url, pk, subtitles, ...}``."""
        html = None
        last = None
        for _ in range(4):
            try:
                resp = self.get(embed_url, headers={"Referer": f"{BASE}/", "Accept": "text/html"})
                if "obfuscation_seed" in resp.text:
                    html = resp.text
                    break
            except Exception as exc:  # Cloudflare intermittents
                last = exc
            time.sleep(1)
        if not html:
            raise RuntimeError(f"could not load flix embed ({last})")

        seed_match = re.search(r'obfuscation_seed:"([^"]+)"', html)
        wp_match = re.search(r'w_payload:"([^"]+)"', html)
        if not seed_match or not wp_match:
            raise RuntimeError("flix embed is missing its crypto payload")
        seed = seed_match.group(1)
        wasm = _b64(wp_match.group(1))

        fields = _field_map(seed)

        def grab(key: str) -> str:
            match = re.search(r'"?' + re.escape(key) + r'"?\s*:\s*"([^"]+)"', html)
            if not match:
                raise RuntimeError(f"flix embed is missing {key}")
            return match.group(1)

        token = grab(fields["tokenField"])
        key_frag2 = grab(fields["keyFrag2Field"])
        frag1_b64 = grab(fields["keyField"])
        iv_b64 = grab(fields["ivField"])

        token_resp = self.get(f"{FLIX}/api/m3u8/{token}",
                              headers={"Referer": embed_url, "Accept": "application/json"})
        token_resp.raise_for_status()
        token_payload = token_resp.json()
        vid_key = _sha256_hex(token + "vid")[:10]
        key_part = _sha256_hex(token + "key")[:10]
        cipher_b64 = token_payload.get(vid_key)
        token_key_b64 = token_payload.get(key_part)
        if not cipher_b64 or not token_key_b64:
            raise RuntimeError("flix token response is incomplete")

        mixed = run_wasm_mix(
            wasm, int(seed[:8], 16),
            _b64(frag1_b64), _b64(key_frag2), _b64(token_key_b64),
        )
        derived = hashlib.pbkdf2_hmac("sha256", mixed, seed.encode(), 1000, dklen=32)
        stream_key = bytearray(derived)
        for idx in range(32):
            stream_key[idx] ^= ord(seed[idx % len(seed)])
        aes_key = hashlib.sha256(bytes(stream_key)).digest()
        plain = AES.new(aes_key, AES.MODE_CBC, _b64(iv_b64)).decrypt(_b64(cipher_b64))
        master_url = plain[:-plain[-1]].decode("utf-8", errors="ignore").strip()
        if not master_url.startswith("http"):
            raise RuntimeError("flix decryption returned no URL")

        subtitles = []
        for sub in re.finditer(r'\{url:"([^"]+)",language:"([^"]+)",format:"([^"]+)"', html):
            subtitles.append({"url": sub.group(1), "language": sub.group(2), "format": sub.group(3)})

        video_match = re.search(r'video_id:"([^"]+)"', html)
        return {
            "master_url": master_url,
            "pk": run_wasm_pk(wasm),
            "subtitles": subtitles,
            "video_id": video_match.group(1) if video_match else "",
            "seed": seed,
        }

    def fetch_playlist(self, url: str, pk: bytes) -> str:
        resp = self.get(url, headers={"Referer": f"{FLIX}/"})
        text = resp.text.strip()
        if text.startswith("#EXTM3U"):
            return text
        return _xor_playlist(text, pk)


# ──────────────────────────────────────────────────────────────────────────────
#  scraper
# ──────────────────────────────────────────────────────────────────────────────


class ReAnimeScraper(BaseScraper):
    """Bot-facing scraper for reanime.to."""

    SOURCE = "reanime"
    BASE = BASE
    impersonate = "chrome124"

    def __init__(self, download_path="anime_downloads", progress_queue=None,
                 client: ReAnimeClient = None):
        super().__init__(download_path, progress_queue)
        self.client = client or ReAnimeClient(impersonate=self.impersonate,
                                              proxy=self.proxy)
        self.session = self.client.session

    # ── search ───────────────────────────────────────────────────────────────

    def search_anime(self, query: str, limit: int = 24) -> list:
        if is_url(query) and detect_source(query) == "reanime":
            try:
                details = self.client.anime_details(self.client.slug_of(query))
            except Exception as exc:
                print(f"reanime url resolve failed: {exc}", flush=True)
                return []
            return [{
                "title": details["title"],
                "id": details["anime_id"],
                "type": details.get("format") or "ANIME",
                "url": f"{BASE}/anime/{details['anime_id']}",
            }]
        return [{
            "title": item["title"],
            "id": item["slug"],
            "type": item.get("type") or "ANIME",
            "url": item["url"],
        } for item in self.client.search(query, limit=limit)]

    # ── episodes ─────────────────────────────────────────────────────────────

    def list_episodes(self, value: str) -> list:
        slug = self.client.slug_of(value)
        details = self.client.anime_details(slug)
        episodes = self.client.episodes(slug)
        out = []
        for episode in episodes:
            out.append({
                "title": episode.get("title") or f"Episode {episode['num']}",
                "url": f"{BASE}/watch/{slug}?ep={episode['num']}",
                "ep_number": str(episode["num"]),
                "ep_id": episode["ep_id"],
                "has_sub": episode.get("sub", False),
                "has_dub": episode.get("dub", False),
                "series_title": details["title"],
            })
        return out

    def get_anime_info(self, anime_id) -> dict:
        try:
            return self.client.anime_details(str(anime_id))
        except Exception:
            return {}

    def get_episode_servers(self, value: str, kind: str = "sub") -> list:
        try:
            details = self.client.anime_details(self.client.slug_of(value))
            servers = self.client.servers(details["anilist_id"], details["mal_id"],
                                          self.client.episode_of(value),
                                          details["themoviedb_id"],
                                          (details.get("external_seasons") or {}).get("tmdb", 1))
            return [s for s in servers if s.get("type") == kind] if kind else servers
        except Exception:
            return []

    def get_home_sections(self) -> dict:
        return {"latest": []}

    def fetch_recently_updated(self, page: int = 1, per_page: int = 20) -> list:
        return []

    def get_schedule(self, date_str: str = None) -> list:
        return []

    # ── download recipe ──────────────────────────────────────────────────────

    def resolve_episode(self, url: str) -> dict:
        slug = self.client.slug_of(url)
        ep = self.client.episode_of(url)
        details = self.client.anime_details(slug)
        episodes = self.client.episodes(slug)
        episode = next((e for e in episodes if e["num"] == ep), None) or (episodes[-1] if episodes else {"num": ep, "title": f"Episode {ep}", "sub": True, "dub": False})
        try:
            servers = self.client.servers(details["anilist_id"], details["mal_id"], ep,
                                          details["themoviedb_id"],
                                          (details.get("external_seasons") or {}).get("tmdb", 1))
        except Exception as exc:
            raise RuntimeError(f"server list failed: {exc}") from exc
        if not servers:
            raise RuntimeError("no servers listed for this episode")

        # Softsub servers first; hardsubs (H-SUB) are only a fallback.
        ordered = sorted(servers, key=lambda s: (
            0 if s.get("name") == "HD-1" else 1 if s.get("name") == "HD-2" else 2,
            0 if s.get("type") == "sub" else 1,
        ))
        embed_url = None
        last_error = None
        for server in ordered:
            try:
                sources = self.client.flix_sources(server["link_id"])
            except Exception as exc:
                last_error = exc
                print(f"   trying {server.get('name')} failed: {exc}", flush=True)
                continue
            if sources.get("master_url"):
                print(f"   -> ok on {server.get('name')}", flush=True)
                embed_url = server["link_id"]
                flix = sources
                break
        if not embed_url:
            raise RuntimeError(f"no stream could be resolved ({last_error})")

        has_dub = any(s.get("type") == "dub" for s in servers)
        recipe = {
            "series": details["title"],
            "slug": slug,
            "season": season_of(details["title"]),
            "episode": str(episode["num"]),
            "ep_title": episode.get("title") or f"Episode {episode['num']}",
            "referer": f"{BASE}/",
            "sub": {
                "file": flix["master_url"],
                "tracks": [],
                "referer": f"{FLIX}/",
            },
            "dub": None,
            "flix": flix,
            "flix_embed": embed_url,
            "has_dub": has_dub,
        }
        return recipe

    # ── direct HLS download (replaces N_m3u8DL-RE for fetch9) ────────────────

    def _prepare(self, source: dict, referer: str, quality) -> dict:  # pragma: no cover - kept for base compat
        return {"url": source.get("file"), "quality": quality, "label": "1080p"}

    def _download_variant(self, variant_url: str, pk: bytes, out_path,
                          *, kind: str, title: str) -> bool:
        """Download one media playlist's segments (AES-128) into ``out_path``."""
        try:
            playlist = self.client.fetch_playlist(variant_url, pk)
        except Exception as exc:
            self.reporter.error(f"could not read playlist: {exc}")
            return False
        key_uri, iv_base = _parse_playlist_key(playlist)
        media_sequence = 0
        seq_match = re.search(r"#EXT-X-MEDIA-SEQUENCE:(\d+)", playlist)
        if seq_match:
            media_sequence = int(seq_match.group(1))
        segments = [line.strip() for line in playlist.splitlines()
                    if line.strip() and not line.startswith("#")]
        if not segments:
            self.reporter.error("playlist has no segments")
            return False

        key = b""
        if key_uri:
            try:
                key_url = urllib.parse.urljoin(variant_url, key_uri)
                resp = self.client.get(key_url, headers={"Referer": f"{FLIX}/"})
                key = resp.content
                if len(key) != 16:
                    self.reporter.error("unexpected stream key")
                    return False
            except Exception as exc:
                self.reporter.error(f"could not fetch stream key: {exc}")
                return False

        total = len(segments)
        downloaded_bytes = 0
        started = time.time()

        def _fetch_segment(item):
            index, raw_uri = item
            seg_url = urllib.parse.urljoin(variant_url, raw_uri)
            # Fresh session per worker: curl_cffi sessions are not thread-safe.
            worker = ReAnimeClient(impersonate=self.impersonate, timeout=self.client.timeout, proxy=self.proxy)
            resp = worker.get(seg_url, headers={"Referer": f"{FLIX}/"})
            data = resp.content
            if key and iv_base is not None:
                iv = (iv_base + media_sequence + index).to_bytes(16, "big")
                data = AES.new(key, AES.MODE_CBC, iv).decrypt(
                    data[:len(data) // 16 * 16])
                # Segments are PKCS#7 padded; without stripping it every
                # boundary would carry junk bytes and break the .ts.
                if data:
                    pad = data[-1]
                    if 1 <= pad <= 16 and data[-pad:] == bytes([pad]) * pad:
                        data = data[:-pad]
            return index, data

        # Fetch in parallel but write in playlist order.
        results: dict[int, bytes] = {}
        workers = 8
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_fetch_segment, (i, uri)): i for i, uri in enumerate(segments)}
            done = 0
            for future in concurrent.futures.as_completed(futures):
                try:
                    index, data = future.result()
                except Exception as exc:
                    print(f"   segment failed: {exc}", flush=True)
                    return False
                results[index] = data
                done += 1
                elapsed = max(time.time() - started, 0.001)
                percent = done / total * 100
                speed_mb = (sum(len(b) for b in results.values()) / elapsed / 1024 / 1024)
                self.reporter.progress(
                    percent=f"{percent:.1f}%",
                    speed=f"{speed_mb:.1f} MB/s",
                    downloaded=f"{sum(len(b) for b in results.values()) / 1024 / 1024:.1f} MB",
                    total="",
                    kind=kind,
                    title=title,
                )
        if len(results) != total:
            self.reporter.error("missing segments")
            return False
        with open(out_path, "wb") as out:
            for index in range(total):
                out.write(results[index])
        return True

    def _download_single(self, url, quality, name_override, season_override,
                         ep_num_override, produced=None):
        try:
            recipe = self.resolve_episode(url)
        except Exception as exc:
            self.reporter.error(str(exc))
            return None
        flix = recipe.get("flix") or {}
        pk = flix.get("pk") or b""
        master_url = (recipe.get("sub") or {}).get("file")
        if not master_url:
            self.reporter.error("no stream found for this episode")
            return None

        series = name_override or recipe.get("series") or "Anime"
        season = str(season_override or recipe.get("season") or "1")
        episode = str(ep_num_override or recipe.get("episode") or "0")
        ep_title = recipe.get("ep_title") or f"Episode {episode}"

        # One encode at 1080p - the site has no other renditions on HD-1.
        qual_label = "1080p"
        base_name = build_basename(
            config_format(),
            season=season, episode=episode, title=series,
            quality=qual_label,
            audio="Dual Audio" if recipe.get("has_dub") else "JP",
        )
        if produced is not None and base_name in produced:
            print(f"{qual_label} is the only variant available - already fetched, skipping",
                  flush=True)
            return qual_label

        from cantarella.scraper.base import _cleanup

        task_dir = self.download_path / f"{self.SOURCE}_{abs(hash(base_name)):x}_{qual_label}"
        task_dir.mkdir(parents=True, exist_ok=True)
        final_file = self.download_path / f"{base_name}.mkv"
        try:
            self.reporter.status(f"📥 **Downloading: {series} [{qual_label}]**\nPlease wait...")
            master = self.client.fetch_playlist(master_url, pk)
            if not master.startswith("#EXTM3U"):
                self.reporter.error("no master playlist")
                return None

            stream_uri = None
            audios = []
            for index, line in enumerate(master.splitlines()):
                if line.startswith("#EXT-X-STREAM-INF"):
                    nxt = master.splitlines()[index + 1].strip()
                    stream_uri = urllib.parse.urljoin(master_url, nxt)
                if line.startswith("#EXT-X-MEDIA:"):
                    uri_match = re.search(r'URI="([^"]+)"', line)
                    lang_match = re.search(r'LANGUAGE="([^"]+)"', line)
                    if uri_match:
                        audios.append((lang_match.group(1) if lang_match else "", uri_match.group(1)))
            if not stream_uri:
                self.reporter.error("master playlist has no video stream")
                return None

            video_path = task_dir / f"{base_name}_sub.ts"
            if not self._download_variant(stream_uri, pk, video_path, kind="sub", title=ep_title):
                self.reporter.error("video download failed")
                return None

            # Audio: Native (jpn) is the primary track, English (eng) is the dub.
            # The video variant carries no audio, so the primary is muxed in first.
            dub_audio = None
            primary_audio = None
            for lang, uri in sorted(audios, key=lambda item: 0 if item[0] == "jpn" else 1):
                abs_uri = urllib.parse.urljoin(master_url, uri)
                suffix = "dub" if lang == "eng" else "native"
                audio_path = task_dir / f"{base_name}_{suffix}.ts"
                ok = self._download_variant(
                    abs_uri, pk, audio_path,
                    kind="dub" if lang == "eng" else "sub", title=ep_title,
                )
                if not ok:
                    print(f"   audio {lang} failed, continuing without it", flush=True)
                    continue
                if lang == "eng":
                    dub_audio = audio_path
                elif primary_audio is None:
                    primary_audio = audio_path

            if primary_audio is not None:
                import subprocess as _subprocess
                merged_ts = task_dir / f"{base_name}_with_native.ts"
                try:
                    proc = _subprocess.run(
                        ["ffmpeg", "-y", "-i", str(video_path), "-i", str(primary_audio),
                         "-c", "copy", str(merged_ts)],
                        capture_output=True,
                    )
                    if proc.returncode == 0 and merged_ts.exists():
                        video_path = merged_ts
                    elif dub_audio is None:
                        dub_audio = primary_audio
                except Exception:
                    if dub_audio is None:
                        dub_audio = primary_audio

            # Subtitles from the embed page (softsubs, not burned in).
            sub_files = []
            if self.session is not None:
                for sub in flix.get("subtitles") or []:
                    url = sub.get("url")
                    if not url:
                        continue
                    try:
                        dest = task_dir / f"{base_name}_{sub.get('language', 'sub').lower().replace(' ', '_')}.vtt"
                        resp = self.client.get(url, headers={"Referer": f"{FLIX}/"})
                        if resp.status_code == 200 and resp.content:
                            dest.write_bytes(resp.content)
                            from cantarella.scraper.base import lang_tag
                            sub_files.append((dest, lang_tag(sub.get("language") or "English")))
                    except Exception as exc:
                        print(f"   subtitle failed: {exc}", flush=True)

            # If the native audio was already merged into video_path, remaining
            # dub_audio is the English track. Otherwise dub_audio holds native.
            merge_tracks(
                video_path, final_file,
                dub_audio=dub_audio,
                subtitles=sub_files,
                audio_lang="jpn",
                reporter=self.reporter,
                title=ep_title,
            )
        finally:
            _cleanup(task_dir)

        produced_path = final_file
        if not produced_path.exists():
            # ``base_name`` contains brackets, so a glob pattern would treat
            # them as character classes; scan the directory instead.
            candidates = [
                p for p in self.download_path.iterdir()
                if p.is_file() and p.name.startswith(base_name) and p.suffix.lower() != ".vtt"
            ]
            candidates.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
            produced_path = candidates[0] if candidates else None
        if not produced_path or not produced_path.exists():
            self.reporter.error("could not produce the final file")
            return None
        if produced is not None:
            produced.add(base_name)
        self.reporter.finished(produced_path, base_name)
        return qual_label


__all__ = ["ReAnimeClient", "ReAnimeScraper"]
