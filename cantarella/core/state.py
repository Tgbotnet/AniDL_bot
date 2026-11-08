#@cantarellabots
# Global storage for URLs per user
current_urls = {}
user_episodes = {} # user_id -> {'anime_title': title, 'episodes': [...], 'url': url} (most recent, legacy compat)
user_search_results = {} # user_id -> search_results (legacy compat, latest search)
user_range_data = {} # user_id -> {'start': int, 'end': int, 'selected_qualities': [], 'msg_id': int}
user_favorites_cache = {} # user_id -> favorites list (for index-based callbacks)

# Token-based menus: every search/favorites/episode menu gets unique short
# tokens so old messages keep working after newer searches (per-user single
# slots overwrote each other and downloaded the wrong anime).
anime_tokens = {}  # token -> {'anime_id': ..., 'source': ..., 'user_id': ...}
_episode_tokens_counter = [0]
episodes_by_msg = {}  # (chat_id, message_id) -> {'title':..., 'episodes': [...], 'url': ..., 'source': ...}

import itertools as _itertools
_token_counter = _itertools.count(1)

def new_anime_token(user_id: int, anime_id: str, source: str) -> str:
    tok = f"{next(_token_counter):x}"
    anime_tokens[tok] = {"user_id": user_id, "anime_id": anime_id, "source": source}
    return tok

# ── Ongoing auto-download toggle ─.─
# ongoing_enabled = False # Can be toggled via /settings
