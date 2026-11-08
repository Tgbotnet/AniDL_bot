#@cantarellabots
from pyrogram.enums import ParseMode
from pyrogram import Client

from pyrogram.types import InlineKeyboardMarkup, Message
from cantarella.button import Button as InlineKeyboardButton
from cantarella.core.anilist import TextEditor, CAPTION_FORMAT
from cantarella.core.utils import encode_data
from config import MAIN_CHANNEL, BOT_TOKEN
import re

async def post_to_main_channel(client: Client, anime_url: str, uploaded_messages: list, quality_map: dict, batch_ep_range: str = None, season_override: str = "1", ep_num_override: str = "1"):
    """
    Creates a post in the MAIN_CHANNEL with AniList metadata and quality buttons.
    uploaded_messages: list of Pyrogram Message objects that were uploaded to TARGET_CHAT_ID.
    quality_map: { '720p': msg_id, '1080p': msg_id, ... }
    batch_ep_range: str, if provided, sets ep_no to this value (e.g., '1-25')
    """
    if not MAIN_CHANNEL:
        return

    # 1. Fetch metadata
    # We need a name to search on AniList. Let's try to extract it from the anime_url or first message title.
    sample_title = "Anime"
    if uploaded_messages:
        # Example title: [S1 - E1] Episode Title [720p] [Dual Audio]
        match = re.search(r'\] (.*?) \[', uploaded_messages[0].caption or "")
        if match:
            sample_title = match.group(1)
        elif uploaded_messages[0].document and uploaded_messages[0].document.file_name:
            match = re.search(r'\] (.*?) \[', uploaded_messages[0].document.file_name)
            if match:
                sample_title = match.group(1)

    te = TextEditor(sample_title)
    await te.load_anilist()
    data = te.adata

    # 2. Format Caption
    # CAPTION_FORMAT: title, anime_season, ep_no, audio, status, t_eps, genres
    # User requested ONLY English name where possible
    title = data.get('title', {}).get('english') or data.get('title', {}).get('romaji') or sample_title

    # Robustness check: if AniList title is completely different from site title,
    # fallback to site title to avoid wrong identification
    from difflib import SequenceMatcher
    similarity = SequenceMatcher(None, sample_title.lower(), title.lower()).ratio()
    # Threshold increased to 0.5 for stricter matching
    if similarity < 0.5:
        title = sample_title
    status = data.get('status', 'Unknown')
    t_eps = data.get('episodes', 'Unknown')
    genres = ", ".join(data.get('genres', [])) or "Unknown"

    # Try to get season and ep_no from the first message
    anime_season = season_override
    ep_no = batch_ep_range if batch_ep_range else ep_num_override

    audio = "Dual Audio"
    if uploaded_messages:
        m = re.search(r'\[S(\d+)-E(\d+)\]', uploaded_messages[0].caption or "")
        if not m:
            m = re.search(r'\[S(\d+) - E(\d+)\]', uploaded_messages[0].caption or "")
        if m:
            anime_season = m.group(1)
            if not batch_ep_range:
                ep_no = m.group(2)
        if "JP" in (uploaded_messages[0].caption or ""):
            audio = "Japanese"
        elif "EN" in (uploaded_messages[0].caption or ""):
            audio = "English"

    caption = CAPTION_FORMAT.format(
        title=title,
        anime_season=anime_season,
        ep_no=ep_no,
        audio=audio,
        status=status,
        t_eps=t_eps,
        genres=genres
    )

    # 3. Create Quality Buttons
    # Each button will be a deep link: t.me/bot?start=base64(msgid_chatid)
    bot_username = (await client.get_me()).username
    buttons = []

    row = []
    for q_label, msg_id in quality_map.items():
        # Encode msg_id and chat_id (TARGET_CHAT_ID)
        chat_id = uploaded_messages[0].chat.id
        payload = encode_data(f"{msg_id}_{chat_id}")
        url = f"https://t.me/{bot_username}?start={payload}"
        row.append(InlineKeyboardButton(q_label, url=url))

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    # 4. Handle Mapped Channel Feature
    from cantarella.core.database import db
    mapped_channel_id = await db.get_mapped_channel(title)

    poster = await te.get_poster()

    # User requirements:
    # 1. Mapped channels upload krke with quality buttons kr
    # 2. Main_channel me sirf download button de kr batch download me aisa hona chahiye ki bot posts me episodes ko 1-12 etc iss trhe hi show kr
    # 3. But mapping channel m har episode ki single post ho or ek settings me toggle button add Krna h ki mapping channels channel me single ki episode post create hogi ya batch me hi upload trke de like 1-12 batch function

    if mapped_channel_id:
        batch_mode = await db.get_user_setting(0, "mapping_batch_mode", True)

        # 4b. Post to Mapped Channel (With Quality Buttons)
        mapped_channel_id_int = int(mapped_channel_id)

        mapped_msg_id = None

        try:
            if batch_mode and batch_ep_range:
                # If batch mode is active and we are in a batch, post the single batch post to the mapped channel with quality buttons
                m_msg = await client.send_photo(
                    chat_id=mapped_channel_id_int,
                    photo=poster,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(buttons), # Quality buttons
                    parse_mode=ParseMode.HTML
                )
                mapped_msg_id = m_msg.id
            elif not batch_ep_range:
                # Single episode download, post single post with quality buttons
                m_msg = await client.send_photo(
                    chat_id=mapped_channel_id_int,
                    photo=poster,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(buttons), # Quality buttons
                    parse_mode=ParseMode.HTML
                )
                mapped_msg_id = m_msg.id
            else:
                # Batch download, but batch_mode is False (User wants single episode posts in mapped channel)

                # Here we need to split the batch into single episodes and post them with their own quality buttons
                # The uploaded_messages might contain multiple qualities for multiple episodes.
                # Group by episode number
                ep_groups = {}
                for msg in uploaded_messages:
                    # Extract episode number
                    m = re.search(r'\[S\d+ - E(\d+)\]', msg.caption or "")
                    if not m:
                        m = re.search(r'\[S\d+-E(\d+)\]', msg.caption or "")

                    if m:
                        ep_idx = m.group(1)
                        if ep_idx not in ep_groups:
                            ep_groups[ep_idx] = []
                        ep_groups[ep_idx].append(msg)
                    else:
                        # Fallback if no episode number found
                        if "unknown" not in ep_groups:
                            ep_groups["unknown"] = []
                        ep_groups["unknown"].append(msg)

                # Now create a post for each episode group
                for ep_idx, msgs in ep_groups.items():
                    # Generate quality buttons for this specific episode
                    ep_quality_map = {}
                    for msg in msgs:
                        # Extract quality
                        q_match = re.search(r'\[(\d+p)\]', msg.caption or "")
                        q_label = q_match.group(1) if q_match else "Auto"
                        ep_quality_map[q_label] = msg.id

                    ep_buttons = []
                    ep_row = []
                    for q_label, msg_id in ep_quality_map.items():
                        chat_id_target = msgs[0].chat.id
                        payload = encode_data(f"{msg_id}_{chat_id_target}")
                        url = f"https://t.me/{bot_username}?start={payload}"
                        ep_row.append(InlineKeyboardButton(q_label, url=url))

                        if len(ep_row) == 2:
                            ep_buttons.append(ep_row)
                            ep_row = []

                    if ep_row:
                        ep_buttons.append(ep_row)

                    # Create a specific caption for this episode
                    ep_caption = CAPTION_FORMAT.format(
                        title=title,
                        anime_season=anime_season,
                        ep_no=ep_idx if ep_idx != "unknown" else ep_no,
                        audio=audio,
                        status=status,
                        t_eps=t_eps,
                        genres=genres
                    )

                    m_msg = await client.send_photo(
                        chat_id=mapped_channel_id_int,
                        photo=poster,
                        caption=ep_caption,
                        reply_markup=InlineKeyboardMarkup(ep_buttons),
                        parse_mode=ParseMode.HTML
                    )
                    if mapped_msg_id is None:
                        mapped_msg_id = m_msg.id

        except Exception as e:
            print(f"Error handling mapped channel: {e}")

        # 4a. Post to Main Channel (Download Only)
        # User requested channel invite link instead of direct message link
        try:
            chat = await client.get_chat(mapped_channel_id_int)
            if chat.username:
                # Public channel link
                mapped_channel_link = f"https://t.me/{chat.username}"
            else:
                # Private channel link (Invite link)
                invite_link = await client.export_chat_invite_link(mapped_channel_id_int)
                mapped_channel_link = invite_link

            main_buttons = [[InlineKeyboardButton("📥 Download", url=mapped_channel_link)]]

            await client.send_photo(
                chat_id=int(MAIN_CHANNEL),
                photo=poster,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(main_buttons),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(f"Error posting to main channel: {e}")

    else:
        # Normal behavior if no mapped channel is found
        try:
            await client.send_photo(
                chat_id=int(MAIN_CHANNEL),
                photo=poster,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(f"Error posting to main channel: {e}")
