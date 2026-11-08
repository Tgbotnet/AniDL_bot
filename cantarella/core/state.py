#@cantarellabots
# Global storage for URLs per user
current_urls = {}
user_episodes = {} # user_id -> {'anime_title': title, 'episodes': [...], 'url': url}
user_search_results = {} # user_id -> search_results
user_range_data = {} # user_id -> {'start': int, 'end': int, 'selected_qualities': [], 'msg_id': int}

# ── Ongoing auto-download toggle ─.─
# ongoing_enabled = False # Can be toggled via /settings
