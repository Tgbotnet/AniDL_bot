#@cantarellabots
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup
from cantarella.button import Button as InlineKeyboardButton

from cantarella.core.state import user_episodes
from cantarella.telegram.download import _handle_download
from cantarella.telegram.pages import post_to_main_channel
from cantarella.core.utils import chunk_list
from config import *
from .helpers import check_fsub, send_fsub_prompt

# ─────────────────────────────────────────────
#  Batch download
# ─────────────────────────────────────────────

@Client.on_callback_query(filters.regex("download_all_opts"))
async def on_download_all_opts(client: Client, callback_query):
    if not await check_fsub(client, callback_query.from_user.id):
        await callback_query.answer("🔒 ᴘʟᴇᴀꜱᴇ ᴊᴏɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ꜰɪʀꜱᴛ!", show_alert=True)
        return await send_fsub_prompt(client, callback_query.message)

    user_id = callback_query.from_user.id
    if user_id not in user_episodes:
        await callback_query.answer("❌ ꜱᴇꜱꜱɪᴏɴ ᴇxᴘɪʀᴇᴅ.")
        return

    user_episodes[user_id].setdefault('selected_qualities', [])
    await show_quality_selection(client, callback_query)


async def show_quality_selection(client: Client, callback_query):
    user_id  = callback_query.from_user.id
    selected = user_episodes[user_id].get('selected_qualities', [])

    def btn(q, label):
        return f"✅ {label}" if q in selected else label

    buttons = [
        [
            InlineKeyboardButton(btn("360",  "360ᴘ"),          callback_data="tq_360"),
            InlineKeyboardButton(btn("720",  "720ᴘ"),          callback_data="tq_720"),
            InlineKeyboardButton(btn("1080", "1080ᴘ"),         callback_data="tq_1080")
        ],
        [InlineKeyboardButton(btn("auto", "ᴀᴜᴛᴏ (ʙᴇꜱᴛ)"),    callback_data="tq_auto")],
        [
            InlineKeyboardButton("✅ ᴅᴏɴᴇ",   callback_data="start_batch_dl"),
            InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel")
        ]
    ]
    await callback_query.edit_message_text(
        "<blockquote>📥 <b>ʙᴀᴛᴄʜ ᴅᴏᴡɴʟᴏᴀᴅ</b>\nꜱᴇʟᴇᴄᴛ ᴛʜᴇ ǫᴜᴀʟɪᴛɪᴇꜱ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ:</blockquote>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


@Client.on_callback_query(filters.regex("^tq_"))
async def on_toggle_quality(client: Client, callback_query):
    user_id = callback_query.from_user.id
    if user_id not in user_episodes:
        await callback_query.answer("❌ ꜱᴇꜱꜱɪᴏɴ ᴇxᴘɪʀᴇᴅ.")
        return

    quality  = callback_query.data.split("_")[1]
    selected = user_episodes[user_id].setdefault('selected_qualities', [])

    if quality in selected:
        selected.remove(quality)
    else:
        selected.append(quality)

    await show_quality_selection(client, callback_query)


@Client.on_callback_query(filters.regex("start_batch_dl"))
async def on_start_batch_dl(client: Client, callback_query):
    if not await check_fsub(client, callback_query.from_user.id):
        await callback_query.answer("🔒 ᴘʟᴇᴀꜱᴇ ᴊᴏɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ꜰɪʀꜱᴛ!", show_alert=True)
        return await send_fsub_prompt(client, callback_query.message)

    user_id = callback_query.from_user.id
    if user_id not in user_episodes:
        await callback_query.answer("❌ ꜱᴇꜱꜱɪᴏɴ ᴇxᴘɪʀᴇᴅ.")
        return

    selected_qualities = user_episodes[user_id].get('selected_qualities', [])
    if not selected_qualities:
        await callback_query.answer("⚠️ ᴘʟᴇᴀꜱᴇ ꜱᴇʟᴇᴄᴛ ᴀᴛ ʟᴇᴀꜱᴛ ᴏɴᴇ ǫᴜᴀʟɪᴛʏ!", show_alert=True)
        return

    episodes = user_episodes[user_id]['episodes']
    await callback_query.answer(f"📥 ꜱᴛᴀʀᴛɪɴɢ ʙᴀᴛᴄʜ ᴅᴏᴡɴʟᴏᴀᴅ ꜰᴏʀ {len(episodes)} ᴇᴘɪꜱᴏᴅᴇꜱ...")
    await callback_query.message.delete()

    quality_priority = {"360": 1, "720": 2, "1080": 3, "auto": 4}
    selected_qualities.sort(key=lambda q: quality_priority.get(q, 99))

    target_chat = int(TARGET_CHAT_ID) if TARGET_CHAT_ID else callback_query.message.chat.id
    status_msg  = await callback_query.message.reply(
        f"<blockquote>🔄 <b>ʙᴀᴛᴄʜ ᴅᴏᴡɴʟᴏᴀᴅ ꜱᴛᴀʀᴛᴇᴅ</b>\nǫᴜᴀʟɪᴛɪᴇꜱ: {', '.join(selected_qualities)}\nᴇᴘɪꜱᴏᴅᴇꜱ: {len(episodes)}</blockquote>",
        parse_mode=ParseMode.HTML
    )

    chunk_size = 25
    for chunk_idx, ep_chunk in enumerate(chunk_list(episodes, chunk_size)):
        start_ep_num = chunk_idx * chunk_size + 1
        end_ep_num   = start_ep_num + len(ep_chunk) - 1
        ep_range_str = f"{start_ep_num}-{end_ep_num}"

        all_chunk_msgs = []
        quality_map    = {}

        for quality in selected_qualities:
            first_msg_id = None
            last_msg_id  = None

            for ep in ep_chunk:
                ep_title = ep['title']
                try:
                    await status_msg.edit_text(
                        f"<blockquote>🔄 <b>ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ᴄʜᴜɴᴋ {ep_range_str}</b>\nǫᴜᴀʟɪᴛʏ: {quality}ᴘ\nᴇᴘɪꜱᴏᴅᴇ: {ep_title}...</blockquote>",
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    pass
                # Pass status_msg so we reuse it and avoid sending new messages to LOG_CHANNEL every time
                msgs, new_status_msg = await _handle_download(
                    client, callback_query.message, ep['url'],
                    status_msg, is_playlist=False, quality=quality, chat_id=target_chat
                )
                if new_status_msg:
                    status_msg = new_status_msg
                await asyncio.sleep(2) # Small delay to avoid flooding when looping
                if msgs:
                    all_chunk_msgs.extend(msgs)
                    for msg in msgs:
                        if first_msg_id is None:
                            first_msg_id = msg.id
                        last_msg_id = msg.id

            if first_msg_id and last_msg_id:
                q_label = f"{quality}p" if quality.isdigit() else "ᴀᴜᴛᴏ"
                quality_map[q_label] = (
                    str(first_msg_id) if first_msg_id == last_msg_id
                    else f"{first_msg_id}-{last_msg_id}"
                )

        if all_chunk_msgs:
            ep_url = ep_chunk[0]['url']
            await post_to_main_channel(client, ep_url, all_chunk_msgs, quality_map, batch_ep_range=ep_range_str)

    await status_msg.edit_text(
        "<blockquote>✅ <b>ʙᴀᴛᴄʜ ᴅᴏᴡɴʟᴏᴀᴅ ᴄᴏᴍᴘʟᴇᴛᴇ!</b></blockquote>",
        parse_mode=ParseMode.HTML
    )

# ─────────────────────────────────────────────
#  Single episode download
# ─────────────────────────────────────────────

@Client.on_callback_query(filters.regex("^dl_"))
async def on_download_quality(client: Client, callback_query):
    if not await check_fsub(client, callback_query.from_user.id):
        await callback_query.answer("🔒 ᴘʟᴇᴀꜱᴇ ᴊᴏɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ꜰɪʀꜱᴛ!", show_alert=True)
        return await send_fsub_prompt(client, callback_query.message)

    parts   = callback_query.data.split("_")
    quality = parts[1]
    ep_idx  = int(parts[2])
    user_id = callback_query.from_user.id

    if user_id not in user_episodes:
        await callback_query.answer("❌ ꜱᴇꜱꜱɪᴏɴ ᴇxᴘɪʀᴇᴅ.")
        return

    ep_data = user_episodes[user_id]['episodes'][ep_idx]
    ep_url = ep_data['url']
    status_msg = await callback_query.message.reply(
        "<blockquote>🔄 ᴘʀᴇᴘᴀʀɪɴɢ ᴅᴏᴡɴʟᴏᴀᴅ...</blockquote>",
        parse_mode=ParseMode.HTML
    )
    target_chat   = int(TARGET_CHAT_ID) if TARGET_CHAT_ID else callback_query.message.chat.id
    uploaded_msgs, _ = await _handle_download(
        client, callback_query.message, ep_url,
        status_msg, quality=quality, chat_id=target_chat
    )

    if uploaded_msgs:
        quality_map = {}
        for msg in uploaded_msgs:
            match = re.search(r'\[(\d+p)\]', msg.caption or "")
            if match:
                quality_map[match.group(1)] = msg.id
            else:
                quality_map[quality] = msg.id
        await post_to_main_channel(client, ep_url, uploaded_msgs, quality_map)
