#@cantarellabots
import asyncio
import re
from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatType
from pyrogram.types import InlineKeyboardMarkup
from cantarella.button import Button as InlineKeyboardButton

from cantarella.core.state import user_episodes, user_search_results, user_range_data
from cantarella.core.database import db
from cantarella.core.images import get_random_image
from config import *
from .helpers import check_fsub, send_fsub_prompt
#@cantarellabots
# ─────────────────────────────────────────────
#  Anime select & episode pagination
# ─────────────────────────────────────────────

@Client.on_callback_query(filters.regex("^anime_"))
async def on_anime_select(client: Client, callback_query):
    if not await check_fsub(client, callback_query.from_user.id):
        await callback_query.answer("🔒 ᴘʟᴇᴀꜱᴇ ᴊᴏɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ꜰɪʀꜱᴛ!", show_alert=True)
        return await send_fsub_prompt(client, callback_query.message)

    anime_id = callback_query.data.split("_")[1]

    active_source = await db.get_user_setting(0, "active_source", "reanime")
    if active_source == "animetsu":
        url = f"https://animetsu.live/anime/{anime_id}"
        from cantarella.scraper.animetsu import AnimetsuScraper
        downloader = AnimetsuScraper()
        entries = await client.loop.run_in_executor(None, downloader.list_episodes, anime_id)
    elif active_source == "reanime":
        url = f"https://reanime.to/anime/{anime_id}"
        from cantarella.scraper.reanime import ReAnimeScraper
        downloader = ReAnimeScraper()
        entries = await client.loop.run_in_executor(None, downloader.list_episodes, url)
    else:
        url = f"https://aniwatchtv.to/watch/{anime_id}"
        from cantarella.scraper.cantarellatv import cantarellatvDownloader
        downloader = cantarellatvDownloader()
        entries = await client.loop.run_in_executor(None, downloader.list_episodes, url)

    if not entries:
        await callback_query.answer("❌ ɴᴏ ᴇᴘɪꜱᴏᴅᴇꜱ ꜰᴏᴜɴᴅ.")
        return

    user_episodes[callback_query.from_user.id] = {
        'title':    entries[0].get('title', 'ᴜɴᴋɴᴏᴡɴ'),
        'episodes': entries,
        'url':      url,
        'page':     0
    }
    await show_episodes_page(client, callback_query, 0)


async def show_episodes_page(client, callback_query, page):
    user_id = callback_query.from_user.id
    data    = user_episodes.get(user_id)
    if not data:
        return

    entries         = data['episodes']
    start           = page * 20
    end             = start + 20
    current_entries = entries[start:end]

    buttons = []
    for i, entry in enumerate(current_entries):
        ep_idx = start + i
        buttons.append([InlineKeyboardButton(f"ᴇᴘɪꜱᴏᴅᴇ {ep_idx+1}", callback_data=f"ep_{ep_idx}")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ ᴘʀᴇᴠ", callback_data=f"eps_page_{page-1}"))
    if end < len(entries):
        nav_row.append(InlineKeyboardButton("ɴᴇxᴛ ➡️", callback_data=f"eps_page_{page+1}"))

    jump_row = []
    if page >= 5:
        jump_row.append(InlineKeyboardButton("⏪ -100 ᴇᴘꜱ", callback_data=f"eps_page_{page-5}"))
    if (page + 5) * 20 < len(entries):
        jump_row.append(InlineKeyboardButton("+100 ᴇᴘꜱ ⏩", callback_data=f"eps_page_{page+5}"))

    if nav_row:
        buttons.append(nav_row)
    if jump_row:
        buttons.append(jump_row)

    # Add Favorite button (Admin Only)
    user_id = callback_query.from_user.id
    is_admin = user_id == OWNER_ID or await db.is_admin(user_id)

    range_btn = InlineKeyboardButton("🔢 ʀᴀɴɢᴇ ᴅᴏᴡɴʟᴏᴀᴅ", callback_data="range_dl_prompt")
    if is_admin:
        favorites = await db.get_favorites(user_id)
        is_fav = any(f['id'] == data['url'].split('/')[-1] for f in favorites)
        fav_btn = InlineKeyboardButton("❤ ʀᴇᴍᴏᴠᴇ ғᴀᴠ", callback_data=f"rem_fav_{data['url'].split('/')[-1]}") if is_fav else InlineKeyboardButton("🤍 ᴀᴅᴅ ғᴀᴠ", callback_data=f"add_fav_{data['url'].split('/')[-1]}")
        buttons.append([fav_btn, range_btn])
    else:
        buttons.append([range_btn])

    buttons.append([
        InlineKeyboardButton("🔙 ʙᴀᴄᴋ",         callback_data="back_to_search"),
        InlineKeyboardButton("📥 ᴅᴏᴡɴʟᴏᴀᴅ ᴀʟʟ", callback_data="download_all_opts"),
        InlineKeyboardButton("❌ ᴄʟᴏꜱᴇ",         callback_data="cancel")
    ])

    try:
        await callback_query.edit_message_caption(
            caption=f"<blockquote>📺 <b>ᴇᴘɪꜱᴏᴅᴇꜱ (ᴘᴀɢᴇ {page+1}):</b>\nꜱᴇʟᴇᴄᴛ ᴀɴ ᴇᴘɪꜱᴏᴅᴇ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ:</blockquote>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
    except:
        await callback_query.edit_message_text(
            f"<blockquote>📺 <b>ᴇᴘɪꜱᴏᴅᴇꜱ (ᴘᴀɢᴇ {page+1}):</b>\nꜱᴇʟᴇᴄᴛ ᴀɴ ᴇᴘɪꜱᴏᴅᴇ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ:</blockquote>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )


@Client.on_callback_query(filters.regex("^eps_page_"))
async def on_eps_page(client: Client, callback_query):
    page = int(callback_query.data.split("_")[2])
    await show_episodes_page(client, callback_query, page)


@Client.on_callback_query(filters.regex("^back_to_search$"))
async def on_back_to_search(client: Client, callback_query):
    user_id = callback_query.from_user.id
    results = user_search_results.get(user_id)
    if not results:
        await callback_query.answer("❌ ꜱᴇᴀʀᴄʜ ʀᴇꜱᴜʟᴛꜱ ᴇxᴘɪʀᴇᴅ.", show_alert=True)
        return

    buttons = []
    for res in results:
        cb_data = f"anime_{res['id']}"
        if len(cb_data) > 64:
            cb_data = cb_data[:64]
        buttons.append([InlineKeyboardButton(f"{res['title']} ({res['type']})", callback_data=cb_data)])

    buttons.append([InlineKeyboardButton("❌ ᴄʟᴏꜱᴇ", callback_data="cancel")])

    keyboard = InlineKeyboardMarkup(buttons)
    try:
        await callback_query.edit_message_caption(
            caption="<blockquote>📺 <b>ꜱᴇᴀʀᴄʜ ʀᴇꜱᴜʟᴛꜱ:</b>\nꜱᴇʟᴇᴄᴛ ᴀɴ ᴀɴɪᴍᴇ:</blockquote>",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    except:
        await callback_query.edit_message_text(
            "<blockquote>📺 <b>ꜱᴇᴀʀᴄʜ ʀᴇꜱᴜʟᴛꜱ:</b>\nꜱᴇʟᴇᴄᴛ ᴀɴ ᴀɴɪᴍᴇ:</blockquote>",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )


@Client.on_callback_query(filters.regex("^add_fav_"))
async def on_add_favorite(client: Client, callback_query):
    user_id = callback_query.from_user.id
    if user_id != OWNER_ID and not await db.is_admin(user_id):
        return await callback_query.answer("❌ ᴛʜɪꜱ ꜰᴇᴀᴛᴜʀᴇ ɪꜱ ꜰᴏʀ ᴀᴅᴍɪɴꜱ ᴏɴʟʏ.", show_alert=True)

    anime_id = callback_query.data.split("_")[2]
    data = user_episodes.get(user_id)
    if not data:
        return await callback_query.answer("❌ ꜱᴇꜱꜱɪᴏɴ ᴇxᴘɪʀᴇᴅ.")

    await db.add_favorite(user_id, anime_id, data['title'])
    await callback_query.answer("✅ ᴀᴅᴅᴇᴅ ᴛᴏ ғᴀᴠᴏʀɪᴛᴇꜱ!", show_alert=True)
    await show_episodes_page(client, callback_query, data.get('page', 0))

@Client.on_callback_query(filters.regex("^rem_fav_"))
async def on_rem_favorite(client: Client, callback_query):
    user_id = callback_query.from_user.id
    if user_id != OWNER_ID and not await db.is_admin(user_id):
        return await callback_query.answer("❌ ᴛʜɪꜱ ꜰᴇᴀᴛᴜʀᴇ ɪꜱ ꜰᴏʀ ᴀᴅᴍɪɴꜱ ᴏɴʟʏ.", show_alert=True)

    anime_id = callback_query.data.split("_")[2]
    await db.remove_favorite(user_id, anime_id)
    await callback_query.answer("❌ ʀᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ ғᴀᴠᴏʀɪᴛᴇꜱ!", show_alert=True)
    data = user_episodes.get(user_id)
    if data:
        await show_episodes_page(client, callback_query, data.get('page', 0))

@Client.on_callback_query(filters.regex("^range_dl_prompt$"))
async def on_range_dl_prompt(client: Client, callback_query):
    user_id = callback_query.from_user.id
    if user_id not in user_episodes:
        return await callback_query.answer("❌ ꜱᴇꜱꜱɪᴏɴ ᴇxᴘɪʀᴇᴅ.")

    from pyrogram.types import ForceReply
    # Telegram requires ForceReply to be sent in a NEW message to reliably trigger the keyboard auto-reply
    prompt = await client.send_message(
        chat_id=callback_query.message.chat.id,
        text="🔢 ᴘʟᴇᴀꜱᴇ ꜱᴇɴᴅ ᴛʜᴇ ʀᴀɴɢᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ.\n\nFᴏʀᴍᴀᴛ: <code>start-end</code> (ᴇ.ɢ., <code>1-12</code>)",
        reply_markup=ForceReply(selective=True),
        parse_mode=ParseMode.HTML
    )
    # Store prompt message ID and original list message ID
    user_range_data[user_id] = {'prompt_id': prompt.id, 'original_msg_id': callback_query.message.id}
    await callback_query.answer()

@Client.on_callback_query(filters.regex("^cancel_range$"))
async def on_cancel_range(client: Client, callback_query):
    user_id = callback_query.from_user.id
    if user_id in user_range_data:
        msg_id = user_range_data[user_id].get('msg_id')
        if msg_id:
            try: await client.delete_messages(callback_query.message.chat.id, msg_id)
            except: pass
        del user_range_data[user_id]
    await callback_query.answer("❌ ʀᴀɴɢᴇ ᴅᴏᴡɴʟᴏᴀᴅ ᴄᴀɴᴄᴇʟʟᴇᴅ.")

@Client.on_message(filters.private & filters.reply)
async def handle_range_input(client: Client, message):
    if not message.reply_to_message:
        return
    reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    if "ᴘʟᴇᴀꜱᴇ ꜱᴇɴᴅ ᴛʜᴇ ʀᴀɴɢᴇ" not in reply_text:
        return

    user_id = message.from_user.id
    # Clean up clutter: delete prompt and user reply
    try:
        await message.delete()
        await message.reply_to_message.delete()
    except: pass

    text = message.text.strip()
    match = re.match(r"(\d+)-(\d+)", text)

    if not match:
        msg = await message.reply("❌ ɪɴᴠᴀʟɪᴅ ғᴏʀᴍᴀᴛ. ᴜꜱᴇ <code>start-end</code> (ᴇ.ɢ., 1-12)")
        await asyncio.sleep(5)
        await msg.delete()
        return

    start, end = int(match.group(1)), int(match.group(2))
    if start > end:
        msg = await message.reply("❌ ꜱᴛᴀʀᴛ ᴇᴘɪꜱᴏᴅᴇ ᴄᴀɴɴᴏᴛ ʙᴇ ɢʀᴇᴀᴛᴇʀ ᴛʜᴀɴ ᴇɴᴅ ᴇᴘɪꜱᴏᴅᴇ.")
        await asyncio.sleep(5)
        await msg.delete()
        return

    user_range_data[user_id] = {'start': start, 'end': end, 'selected_qualities': []}
    await show_range_quality_selection(client, message, start, end, user_id=user_id)

async def show_range_quality_selection(client, message, start, end, edit=False, user_id=None):
    if user_id is None:
        if hasattr(message, 'from_user') and message.from_user and not message.from_user.is_bot:
            user_id = message.from_user.id
        elif message.chat and message.chat.type == ChatType.PRIVATE:
            user_id = message.chat.id
        else:
            user_id = message.chat.id

    if user_id not in user_range_data:
         user_range_data[user_id] = {'start': start, 'end': end, 'selected_qualities': []}

    selected = user_range_data[user_id].get('selected_qualities', [])

    def btn(q, label):
        return f"✅ {label}" if q in selected else label

    buttons = [
        [
            InlineKeyboardButton(btn("360", "360ᴘ"), callback_data="trq_360"),
            InlineKeyboardButton(btn("720", "720ᴘ"), callback_data="trq_720"),
            InlineKeyboardButton(btn("1080", "1080ᴘ"), callback_data="trq_1080")
        ],
        [InlineKeyboardButton(btn("auto", "ᴀᴜᴛᴏ (ʙᴇꜱᴛ)"), callback_data="trq_auto")],
        [
            InlineKeyboardButton("✅ ᴅᴏɴᴇ", callback_data="start_range_dl"),
            InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_range")
        ]
    ]

    text = f"<blockquote>🔢 <b>ʀᴀɴɢᴇ ꜱᴇʟᴇᴄᴛᴇᴅ:</b> {start}-{end}\nꜱᴇʟᴇᴄᴛ ǫᴜᴀʟɪᴛɪᴇꜱ:</blockquote>"
    if edit:
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    else:
        new_msg = await client.send_message(message.chat.id, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        user_range_data[user_id]['msg_id'] = new_msg.id

@Client.on_callback_query(filters.regex("^trq_"))
async def on_toggle_range_quality(client: Client, callback_query):
    user_id = callback_query.from_user.id
    if user_id not in user_range_data:
        # Try to recover from message
        msg_text = callback_query.message.text or callback_query.message.caption or ""
        m = re.search(r"ʀᴀɴɢᴇ ꜱᴇʟᴇᴄᴛᴇᴅ:</b> (\d+)-(\d+)", msg_text)
        if m:
            user_range_data[user_id] = {'start': int(m.group(1)), 'end': int(m.group(2)), 'selected_qualities': []}
        else:
            return await callback_query.answer("❌ ꜱᴇꜱꜱɪᴏɴ ᴇxᴘɪʀᴇᴅ. ᴘʟᴇᴀꜱᴇ ꜱᴇɴᴅ ᴛʜᴇ ʀᴀɴɢᴇ ᴀɢᴀɪɴ.", show_alert=True)

    quality = callback_query.data.split("_")[1]
    selected = user_range_data[user_id].setdefault('selected_qualities', [])

    if quality in selected:
        selected.remove(quality)
    else:
        selected.append(quality)

    range_data = user_range_data[user_id]
    await show_range_quality_selection(client, callback_query.message, range_data['start'], range_data['end'], edit=True, user_id=user_id)

@Client.on_callback_query(filters.regex("^start_range_dl$"))
async def on_start_range_dl(client: Client, callback_query):
    if not await check_fsub(client, callback_query.from_user.id):
        await callback_query.answer("🔒 ᴘʟᴇᴀꜱᴇ ᴊᴏɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ꜰɪʀꜱᴛ!", show_alert=True)
        return await send_fsub_prompt(client, callback_query.message)

    user_id = callback_query.from_user.id
    if user_id not in user_range_data:
        # Try to recover
        msg_text = callback_query.message.text or callback_query.message.caption or ""
        m = re.search(r"ʀᴀɴɢᴇ ꜱᴇʟᴇᴄᴛᴇᴅ:</b> (\d+)-(\d+)", msg_text)
        if m:
             # We still need qualities from somewhere, but they should be in the buttons...
             # Actually if user_range_data is gone, selected_qualities is gone too.
             pass
        return await callback_query.answer("❌ ꜱᴇꜱꜱɪᴏɴ ᴇxᴘɪʀᴇᴅ.", show_alert=True)

    if user_id not in user_episodes:
        return await callback_query.answer("❌ ꜱᴇꜱꜱɪᴏɴ ᴇxᴘɪʀᴇᴅ. ᴘʟᴇᴀꜱᴇ ꜱᴇᴀʀᴄʜ ᴀɴɪᴍᴇ ᴀɢᴀɪɴ.", show_alert=True)

    range_data = user_range_data[user_id]
    qualities = range_data.get('selected_qualities', [])
    if not qualities:
        return await callback_query.answer("⚠️ ᴘʟᴇᴀꜱᴇ ꜱᴇʟᴇᴄᴛ ᴀᴛ ʟᴇᴀꜱᴛ ᴏɴᴇ ǫᴜᴀʟɪᴛʏ!", show_alert=True)

    start, end = range_data['start'], range_data['end']

    all_episodes = user_episodes[user_id]['episodes']
    selected_episodes = []

    for ep in all_episodes:
        try:
            ep_num = int(ep.get('ep_number', 0))
            if start <= ep_num <= end:
                selected_episodes.append(ep)
        except:
            pass

    if not selected_episodes:
        return await callback_query.answer("❌ ɴᴏ ᴇᴘɪꜱᴏᴅᴇꜱ ғᴏᴜɴᴅ ɪɴ ᴛʜɪꜱ ʀᴀɴɢᴇ.", show_alert=True)

    await callback_query.answer(f"📥 ꜱᴛᴀʀᴛɪɴɢ ʀᴀɴɢᴇ ᴅᴏᴡɴʟᴏᴀᴅ ғᴏʀ {len(selected_episodes)} ᴇᴘɪꜱᴏᴅᴇꜱ...")
    try: await callback_query.message.delete()
    except: pass

    from cantarella.telegram.download import _handle_download
    from cantarella.telegram.pages import post_to_main_channel
    from cantarella.core.utils import chunk_list

    target_chat = int(TARGET_CHAT_ID) if TARGET_CHAT_ID else callback_query.message.chat.id
    status_msg  = await callback_query.message.reply(
        f"<blockquote>🔢 <b>ʀᴀɴɢᴇ ᴅᴏᴡɴʟᴏᴀᴅ ꜱᴛᴀʀᴛᴇᴅ</b>\nǫᴜᴀʟɪᴛɪᴇꜱ: {', '.join(qualities)}\nʀᴀɴɢᴇ: {start}-{end}</blockquote>",
        parse_mode=ParseMode.HTML
    )

    quality_priority = {"360": 1, "720": 2, "1080": 3, "auto": 4}
    qualities.sort(key=lambda q: quality_priority.get(q, 99))

    chunk_size = 25
    for chunk_idx, ep_chunk in enumerate(chunk_list(selected_episodes, chunk_size)):
        ep_range_str = f"{ep_chunk[0]['ep_number']}-{ep_chunk[-1]['ep_number']}"
        all_chunk_msgs = []
        quality_map = {}

        for q in qualities:
            first_id = None
            last_id = None
            for ep in ep_chunk:
                try:
                    await status_msg.edit_text(f"<blockquote>🔄 ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ {ep['title']} [{q}p]...</blockquote>", parse_mode=ParseMode.HTML)
                except: pass

                msgs, new_status = await _handle_download(client, None, ep['url'], status_msg, quality=q, chat_id=target_chat)
                if new_status: status_msg = new_status
                if msgs:
                    all_chunk_msgs.extend(msgs)
                    for m in msgs:
                        if first_id is None: first_id = m.id
                        last_id = m.id

            if first_id and last_id:
                q_label = f"{q}p" if q.isdigit() else "ᴀᴜᴛᴏ"
                quality_map[q_label] = str(first_id) if first_id == last_id else f"{first_id}-{last_id}"

        if all_chunk_msgs:
            await post_to_main_channel(client, ep_chunk[0]['url'], all_chunk_msgs, quality_map, batch_ep_range=ep_range_str)

    await status_msg.edit_text("<blockquote>✅ <b>ʀᴀɴɢᴇ ᴅᴏᴡɴʟᴏᴀᴅ ᴄᴏᴍᴘʟᴇᴛᴇ!</b></blockquote>", parse_mode=ParseMode.HTML)

@Client.on_callback_query(filters.regex("^favorites$"))
async def on_favorites_cb(client: Client, callback_query):
    user_id = callback_query.from_user.id
    if user_id != OWNER_ID and not await db.is_admin(user_id):
        return await callback_query.answer("❌ ᴛʜɪꜱ ꜰᴇᴀᴛᴜʀᴇ ɪꜱ ꜰᴏʀ ᴀᴅᴍɪɴꜱ ᴏɴʟʏ.", show_alert=True)

    favorites = await db.get_favorites(user_id)

    if not favorites:
        return await callback_query.answer("❤ ʏᴏᴜʀ ғᴀᴠᴏʀɪᴛᴇꜱ ʟɪꜱᴛ ɪꜱ ᴇᴍᴘᴛʏ.", show_alert=True)

    buttons = []
    for fav in favorites:
        buttons.append([InlineKeyboardButton(fav['title'], callback_data=f"anime_{fav['id']}")])

    buttons.append([InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="start"), InlineKeyboardButton("❌ ᴄʟᴏꜱᴇ", callback_data="close")])

    await callback_query.edit_message_caption(
        caption="<blockquote>❤ <b>ʏᴏᴜʀ ғᴀᴠᴏʀɪᴛᴇ ᴀɴɪᴍᴇꜱ:</b></blockquote>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

@Client.on_callback_query(filters.regex("^ep_"))
async def on_episode_select(client: Client, callback_query):
    if not await check_fsub(client, callback_query.from_user.id):
        await callback_query.answer("🔒 ᴘʟᴇᴀꜱᴇ ᴊᴏɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ꜰɪʀꜱᴛ!", show_alert=True)
        return await send_fsub_prompt(client, callback_query.message)

    ep_idx  = int(callback_query.data.split("_")[1])
    user_id = callback_query.from_user.id
    if user_id not in user_episodes:
        await callback_query.answer("❌ ꜱᴇꜱꜱɪᴏɴ ᴇxᴘɪʀᴇᴅ.")
        return

    page = ep_idx // 20
    buttons = [
        [
            InlineKeyboardButton("360ᴘ",  callback_data=f"dl_360_{ep_idx}"),
            InlineKeyboardButton("720ᴘ",  callback_data=f"dl_720_{ep_idx}"),
            InlineKeyboardButton("1080ᴘ", callback_data=f"dl_1080_{ep_idx}")
        ],
        [InlineKeyboardButton("ᴀᴜᴛᴏ (ʙᴇꜱᴛ)",    callback_data=f"dl_auto_{ep_idx}")],
        [InlineKeyboardButton("ᴀʟʟ ǫᴜᴀʟɪᴛɪᴇꜱ", callback_data=f"dl_all_{ep_idx}")],
        [
            InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data=f"eps_page_{page}"),
            InlineKeyboardButton("❌ ᴄʟᴏꜱᴇ", callback_data="cancel")
        ]
    ]
    try:
        await callback_query.edit_message_caption(
            caption=f"<blockquote>📥 <b>ᴅᴏᴡɴʟᴏᴀᴅ ᴇᴘɪꜱᴏᴅᴇ {ep_idx+1}</b>\nꜱᴇʟᴇᴄᴛ ǫᴜᴀʟɪᴛʏ:</blockquote>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
    except:
        await callback_query.edit_message_text(
            f"<blockquote>📥 <b>ᴅᴏᴡɴʟᴏᴀᴅ ᴇᴘɪꜱᴏᴅᴇ {ep_idx+1}</b>\nꜱᴇʟᴇᴄᴛ ǫᴜᴀʟɪᴛʏ:</blockquote>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
