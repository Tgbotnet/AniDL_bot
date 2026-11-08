#@cantarellabots
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup
from cantarella.button import Button as InlineKeyboardButton
import asyncio
import re

from cantarella.core.database import db
from cantarella.core.images import get_random_image
from cantarella.scraper.search import search_anime
from cantarella.scraper.cantarellatv import cantarellatvDownloader
from cantarella.core.state import current_urls, user_search_results
from cantarella.telegram.download import _handle_download
from config import OWNER_ID, TARGET_CHAT_ID

@Client.on_message(filters.private & filters.text & ~filters.regex(r"^/"))
async def handle_url(client: Client, message):
    url = message.text.strip()

    # --- Access Control ---
    is_admin = await db.is_admin(message.from_user.id)
    if message.from_user.id != OWNER_ID and not is_admin:
        return await message.reply("<blockquote>❌ <b>ᴏɴʟʏ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴀᴅᴍɪɴɪꜱᴛʀᴀᴛᴏʀꜱ ᴄᴀɴ ꜱᴇᴀʀᴄʜ ᴏʀ ᴅᴏᴡɴʟᴏᴀᴅ ᴀɴɪᴍᴇ.</b>\n\nᴄᴏɴᴛᴀᴄᴛ ᴛʜᴇ ᴏᴡɴᴇʀ ɪғ ʏᴏᴜ ᴛʜɪɴᴋ ᴛʜɪꜱ ɪꜱ ᴀ ᴍɪꜱᴛᴀᴋᴇ.</blockquote>", parse_mode=ParseMode.HTML)

    is_animetsu = "animetsu.live" in url.lower() or "animetsu.bz" in url.lower()
    is_reanime = "reanime.to" in url.lower() or "flixcloud.cc" in url.lower()

    if "hianime" not in url.lower() and "cantarella" not in url.lower() and "aniwatchtv.to" not in url.lower() and not is_animetsu and not is_reanime:
        # Treat as a search query
        status_msg = await client.send_photo(
            message.chat.id,
            photo=get_random_image(),
            caption="<blockquote>🔍 <b>ꜱᴇᴀʀᴄʜɪɴɢ ᴀɴɪᴍᴇ, ᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ...</b></blockquote>",
            parse_mode=ParseMode.HTML
        )
        active_source = await db.get_user_setting(0, "active_source", "reanime")
        results = await asyncio.to_thread(search_anime, url, source=active_source)
        if not results:
            await status_msg.edit_caption("<blockquote>❌ <b>ɴᴏ ᴀɴɪᴍᴇ ғᴏᴜɴᴅ ғᴏʀ ʏᴏᴜʀ ǫᴜᴇʀʏ.</b>\nᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ᴜʀʟ ᴏʀ ᴛʀʏ ᴀɴᴏᴛʜᴇʀ ꜱᴇᴀʀᴄʜ.</blockquote>", parse_mode=ParseMode.HTML)
            return

        user_search_results[message.from_user.id] = results

        buttons = []
        for res in results:
            cb_data = f"anime_{res['id']}"
            if len(cb_data) > 64:
                cb_data = cb_data[:64]

            buttons.append([InlineKeyboardButton(f"{res['title']} ({res['type']})", callback_data=cb_data)])

        buttons.append([InlineKeyboardButton("❌ ᴄʟᴏꜱᴇ", callback_data="cancel")])

        keyboard = InlineKeyboardMarkup(buttons)
        await status_msg.edit_caption(
            caption="<blockquote>📺 <b>ꜱᴇᴀʀᴄʜ ʀᴇꜱᴜʟᴛꜱ:</b>\nꜱᴇʟᴇᴄᴛ ᴀɴ ᴀɴɪᴍᴇ:</blockquote>",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        return

    is_episode = "ep=" in url or "episode-" in url or (is_animetsu and "/watch/" in url) or (is_reanime and "/watch/" in url)

    if is_episode:
        from cantarella.telegram.pages import post_to_main_channel
        status_msg = await client.send_photo(
            message.chat.id,
            photo=get_random_image(),
            caption="<blockquote>🔄 <b>ᴘʀᴇᴘᴀʀɪɴɢ ᴅᴏᴡɴʟᴏᴀᴅ...</b></blockquote>",
            parse_mode=ParseMode.HTML
        )
        target_chat = int(TARGET_CHAT_ID) if TARGET_CHAT_ID else message.chat.id
        uploaded_msgs, _ = await _handle_download(client, message, url, status_msg, is_playlist=False, quality="all", chat_id=target_chat)

        if uploaded_msgs:
            quality_map = {}
            for msg in uploaded_msgs:
                match = re.search(r'\[(\d+p)\]', msg.caption or "")
                if match:
                    quality_map[match.group(1)] = msg.id
                else:
                    quality_map["Auto"] = msg.id

            await post_to_main_channel(client, url, uploaded_msgs, quality_map)
    else:
        active_source = await db.get_user_setting(0, "active_source", "reanime")
        if is_animetsu:
            from cantarella.scraper.animetsu import AnimetsuScraper
            entries = await asyncio.to_thread(AnimetsuScraper().list_episodes, url)
        elif is_reanime:
            from cantarella.scraper.reanime import ReAnimeScraper
            entries = await asyncio.to_thread(ReAnimeScraper().list_episodes, url)
        else:
            entries = await asyncio.to_thread(cantarellatvDownloader().list_episodes, url)

        if not entries:
            await client.send_photo(
                message.chat.id,
                photo=get_random_image(),
                caption="<blockquote>❌ <b>ғᴀɪʟᴇᴅ ᴛᴏ ғᴇᴛᴄʜ ᴇᴘɪꜱᴏᴅᴇꜱ.</b></blockquote>",
                parse_mode=ParseMode.HTML
            )
            return

        count = len(entries)
        anime_title = entries[0].get('title', 'Unknown') if entries else 'Unknown'

        text = f"<blockquote>📺 <b>ᴀɴɪᴍᴇ:</b> {anime_title}\n"
        text += f"📼 <b>ᴛᴏᴛᴀʟ ᴇᴘɪꜱᴏᴅᴇꜱ:</b> {count}\n\n"
        text += "<b>ᴇᴘɪꜱᴏᴅᴇꜱ:</b>\n"
        for idx, entry in enumerate(entries, 1):
            ep_title = entry.get('title', f'Episode {idx}')
            text += f" {idx}. {ep_title}\n"
        text += "</blockquote>"

        await client.send_photo(
            message.chat.id,
            photo=get_random_image(),
            caption=text,
            parse_mode=ParseMode.HTML
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 ᴅᴏᴡɴʟᴏᴀᴅ ᴀʟʟ", callback_data="download_all")],
            [InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel")]
        ])
        await message.reply("<blockquote>ᴄʜᴏᴏꜱᴇ ᴀɴ ᴏᴘᴛɪᴏɴ:</blockquote>", reply_markup=keyboard, parse_mode=ParseMode.HTML)

        current_urls[message.from_user.id] = url
