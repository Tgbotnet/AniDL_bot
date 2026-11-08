#@cantarellabots
from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatMemberStatus
import time
import sys
import os
import asyncio
import psutil
import platform

from cantarella.core.database import db
from config import OWNER_ID

async def check_admin(filter, client, message):
    try:
        user_id = message.from_user.id
        if user_id == OWNER_ID:
            return True
        return await db.is_admin(user_id)
    except Exception:
        return False

admin = filters.create(check_admin)

@Client.on_message(filters.private & filters.command("setmap"))
async def handle_setmap(client: Client, message):
    if message.from_user.id != OWNER_ID:
        is_admin = await db.is_admin(message.from_user.id)
        if not is_admin:
            return await message.reply("<blockquote>❌ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ɪꜱ ғᴏʀ ᴀᴅᴍɪɴɪꜱᴛʀᴀᴛᴏʀꜱ ᴏɴʟʏ.</blockquote>", parse_mode=ParseMode.HTML)

    if len(message.command) < 3:
        return await message.reply("<blockquote>❌ ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴄʜᴀɴɴᴇʟ ɪᴅ ᴀɴᴅ ᴀɴɪᴍᴇ ɴᴀᴍᴇ.\nᴜꜱᴀɢᴇ: <code>/setmap -100xxxxxxxx Anime Name</code></blockquote>", parse_mode=ParseMode.HTML)

    try:
        chat_id = int(message.command[1])
    except ValueError:
        return await message.reply("<blockquote>❌ ɪɴᴠᴀʟɪᴅ ᴄʜᴀɴɴᴇʟ ɪᴅ.</blockquote>", parse_mode=ParseMode.HTML)

    anime_name = " ".join(message.command[2:])
    await db.set_mapped_channel(anime_name, chat_id)

    try:
        chat = await client.get_chat(chat_id)
        chat_title = chat.title
    except Exception:
        chat_title = "Unknown Channel"

    await message.reply(f"<blockquote>✅ <b>ᴍᴀᴘᴘɪɴɢ ꜱᴇᴛ:</b>\nᴀɴɪᴍᴇ: <code>{anime_name}</code>\nᴄʜᴀɴɴᴇʟ: <code>{chat_title} ({chat_id})</code></blockquote>", parse_mode=ParseMode.HTML)

@Client.on_message(filters.private & filters.command("maplist"))
async def handle_maplist(client: Client, message):
    if message.from_user.id != OWNER_ID:
        is_admin = await db.is_admin(message.from_user.id)
        if not is_admin:
            return await message.reply("<blockquote>❌ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ɪꜱ ғᴏʀ ᴀᴅᴍɪɴɪꜱᴛʀᴀᴛᴏʀꜱ ᴏɴʟʏ.</blockquote>", parse_mode=ParseMode.HTML)

    mappings = await db.get_all_mappings()
    if not mappings:
        return await message.reply("<blockquote>📋 <b>ɴᴏ ᴍᴀᴘᴘɪɴɢꜱ ғᴏᴜɴᴅ.</b></blockquote>", parse_mode=ParseMode.HTML)

    text = "<blockquote>📋 <b>ᴀɴɪᴍᴇ ᴍᴀᴘᴘɪɴɢꜱ:</b>\n\n"
    for m in mappings:
        names = ", ".join(m.get('anime_names', []))
        text += f"• <code>{m['_id']}</code>: {names}\n"
    text += "</blockquote>"

    await message.reply(text, parse_mode=ParseMode.HTML)

@Client.on_message(filters.private & filters.command("unmap"))
async def handle_unmap(client: Client, message):
    if message.from_user.id != OWNER_ID:
        is_admin = await db.is_admin(message.from_user.id)
        if not is_admin:
            return await message.reply("<blockquote>❌ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ɪꜱ ғᴏʀ ᴀᴅᴍɪɴɪꜱᴛʀᴀᴛᴏʀꜱ ᴏɴʟʏ.</blockquote>", parse_mode=ParseMode.HTML)

    if len(message.command) < 2:
        return await message.reply("<blockquote>❌ ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴄʜᴀɴɴᴇʟ ɪᴅ.\nᴜꜱᴀɢᴇ: <code>/unmap -100xxxxxxxx</code></blockquote>", parse_mode=ParseMode.HTML)

    try:
        chat_id = int(message.command[1])
    except ValueError:
        return await message.reply("<blockquote>❌ ɪɴᴠᴀʟɪᴅ ᴄʜᴀɴɴᴇʟ ɪᴅ.</blockquote>", parse_mode=ParseMode.HTML)

    await db.remove_mapped_channel(chat_id)

    try:
        chat = await client.get_chat(chat_id)
        chat_title = chat.title
    except Exception:
        chat_title = "Unknown Channel"

    await message.reply(f"<blockquote>✅ <b>ᴍᴀᴘᴘɪɴɢ ʀᴇᴍᴏᴠᴇᴅ ғᴏʀ ᴄʜᴀɴɴᴇʟ:</b> <code>{chat_title} ({chat_id})</code></blockquote>", parse_mode=ParseMode.HTML)

@Client.on_message(filters.private & filters.command("add_admin"))
async def handle_add_admin(client: Client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("<blockquote>❌ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ɪꜱ ᴏɴʟʏ ғᴏʀ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ.</blockquote>", parse_mode=ParseMode.HTML)

    user_id = None
    user_name = "Admin"

    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.first_name
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
        except ValueError:
            return await message.reply("<blockquote>❌ ɪɴᴠᴀʟɪᴅ ᴜꜱᴇʀ ɪᴅ.</blockquote>", parse_mode=ParseMode.HTML)

    if not user_id:
        return await message.reply("<blockquote>❌ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜꜱᴇʀ'ꜱ ᴍᴇꜱꜱᴀɢᴇ ᴏʀ ᴘʀᴏᴠɪᴅᴇ ᴛʜᴇɪʀ ᴜꜱᴇʀ ɪᴅ.</blockquote>", parse_mode=ParseMode.HTML)

    await db.add_admin(user_id, user_name)
    await message.reply(f"<blockquote>✅ <b>ᴀᴅᴍɪɴ ᴀᴅᴅᴇᴅ:</b> {user_name} (<code>{user_id}</code>)</blockquote>", parse_mode=ParseMode.HTML)

@Client.on_message(filters.private & filters.command("rm_admin"))
async def handle_rm_admin(client: Client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("<blockquote>❌ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ɪꜱ ᴏɴʟʏ ғᴏʀ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ.</blockquote>", parse_mode=ParseMode.HTML)

    user_id = None
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
        except ValueError:
            return await message.reply("<blockquote>❌ ɪɴᴠᴀʟɪᴅ ᴜꜱᴇʀ ɪᴅ.</blockquote>", parse_mode=ParseMode.HTML)

    if not user_id:
        return await message.reply("<blockquote>❌ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜꜱᴇʀ'ꜱ ᴍᴇꜱꜱᴀɢᴇ ᴏʀ ᴘʀᴏᴠɪᴅᴇ ᴛʜᴇɪʀ ᴜꜱᴇʀ ɪᴅ.</blockquote>", parse_mode=ParseMode.HTML)

    await db.remove_admin(user_id)
    await message.reply(f"<blockquote>✅ <b>ᴀᴅᴍɪɴ ʀᴇᴍᴏᴠᴇᴅ:</b> <code>{user_id}</code></blockquote>", parse_mode=ParseMode.HTML)

@Client.on_message(filters.private & filters.command("admins"))
async def handle_admins_list(client: Client, message):
    is_admin = await db.is_admin(message.from_user.id)
    if message.from_user.id != OWNER_ID and not is_admin:
        return await message.reply("<blockquote>❌ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ɪꜱ ғᴏʀ ᴀᴅᴍɪɴɪꜱᴛʀᴀᴛᴏʀꜱ ᴏɴʟʏ.</blockquote>", parse_mode=ParseMode.HTML)

    admins = await db.get_all_admins()
    if not admins:
        return await message.reply("<blockquote>📋 <b>ɴᴏ ᴀᴅᴍɪɴꜱ ᴀᴅᴅᴇᴅ ʏᴇᴛ.</b></blockquote>", parse_mode=ParseMode.HTML)

    text = "<blockquote>📋 <b>ʙᴏᴛ ᴀᴅᴍɪɴɪꜱᴛʀᴀᴛᴏʀꜱ:</b>\n\n"
    text += f"👑 <b>ᴏᴡɴᴇʀ:</b> <code>{OWNER_ID}</code>\n"
    for admin_doc in admins:
        admin_name = admin_doc.get('name', 'Admin')
        text += f"• {admin_name}: <code>{admin_doc['_id']}</code>\n"
    text += "</blockquote>"

    await message.reply(text, parse_mode=ParseMode.HTML)

@Client.on_message(filters.private & filters.command("users"))
async def handle_users_count(client: Client, message):
    is_admin = await db.is_admin(message.from_user.id)
    if message.from_user.id != OWNER_ID and not is_admin:
        return await message.reply("<blockquote>❌ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ɪꜱ ғᴏʀ ᴀᴅᴍɪɴɪꜱᴛʀᴀᴛᴏʀꜱ ᴏɴʟʏ.</blockquote>", parse_mode=ParseMode.HTML)

    count = await db.get_user_count()
    await message.reply(f"<blockquote>📊 <b>ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ:</b> <code>{count}</code></blockquote>", parse_mode=ParseMode.HTML)

@Client.on_message(filters.private & filters.command("stats"))
async def handle_stats(client: Client, message):
    is_admin = await db.is_admin(message.from_user.id)
    if message.from_user.id != OWNER_ID and not is_admin:
        return await message.reply("<blockquote>❌ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ɪꜱ ғᴏʀ ᴀᴅᴍɪɴɪꜱᴛʀᴀᴛᴏʀꜱ ᴏɴʟʏ.</blockquote>", parse_mode=ParseMode.HTML)

    sts = await message.reply("<blockquote>📊 <b>ғᴇᴛᴄʜɪɴɢ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ...</b></blockquote>", parse_mode=ParseMode.HTML)

    total_users = await db.get_user_count()
    total_admins = len(await db.get_all_admins()) + 1 # +1 for owner
    processed_eps = await db.get_processed_count()
    ongoing_enabled = await db.get_user_setting(0, "ongoing_enabled", False)

    # Storage Stats
    def fmt(b):
        if b < 1024*1024: return f"{b/1024:.2f} KB"
        if b < 1024*1024*1024: return f"{b/(1024*1024):.2f} MB"
        return f"{b/(1024*1024*1024):.2f} GB"

    def get_bar(percent):
        filled = int(percent / 10)
        return "▰" * filled + "▱" * (10 - filled)

    # Storage Stats
    storage_info = ""
    db_stats = await db.get_db_stats()
    if db_stats:
        used_bytes = db_stats['storage_size']
        total_bytes = 512 * 1024 * 1024 # 512MB for Atlas M0
        percent = (used_bytes / total_bytes) * 100
        storage_info = (
            f"\n\n🗄️ <b>ᴅᴀᴛᴀʙᴀꜱᴇ ꜱᴛᴏʀᴀɢᴇ:</b>\n"
            f"<code>{get_bar(percent)}</code> {percent:.1f}%\n"
            f"<b>ᴜꜱᴇᴅ:</b> <code>{fmt(used_bytes)}</code> / <b>ᴛᴏᴛᴀʟ:</b> <code>512.00 MB</code>"
        )

    # System Stats
    cpu_usage = psutil.cpu_percent()
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    sys_info = (
        f"\n\n🖥️ <b>ꜱʏꜱᴛᴇᴍ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ:</b>\n"
        f"<b>ᴄᴘᴜ:</b> <code>{get_bar(cpu_usage)}</code> {cpu_usage}%\n"
        f"<b>ʀᴀᴍ:</b> <code>{get_bar(ram.percent)}</code> {ram.percent}%\n"
        f"<b>ᴜꜱᴇᴅ:</b> <code>{fmt(ram.used)}</code> / <b>ᴛᴏᴛᴀʟ:</b> <code>{fmt(ram.total)}</code>\n"
        f"<b>ᴅɪꜱᴋ:</b> <code>{get_bar(disk.percent)}</code> {disk.percent}%\n"
        f"<b>ᴜꜱᴇᴅ:</b> <code>{fmt(disk.used)}</code> / <b>ᴛᴏᴛᴀʟ:</b> <code>{fmt(disk.total)}</code>"
    )

    # System Specs
    specs = (
        f"\n\n⚙️ <b>ꜱʏꜱᴛᴇᴍ ꜱᴘᴇᴄɪғɪᴄᴀᴛɪᴏɴꜱ:</b>\n"
        f"<b>ᴏꜱ:</b> <code>{platform.system()} {platform.release()}</code>\n"
        f"<b>ᴀʀᴄʜ:</b> <code>{platform.machine()}</code>\n"
        f"<b>ᴘʏᴛʜᴏɴ:</b> <code>{platform.python_version()}</code>"
    )

    text = (
        "<blockquote>📊 <b>ʙᴏᴛ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ</b>\n\n"
        f"👤 <b>ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ:</b> <code>{total_users}</code>\n"
        f"🛡️ <b>ᴛᴏᴛᴀʟ ᴀᴅᴍɪɴꜱ:</b> <code>{total_admins}</code>\n"
        f"📼 <b>ᴇᴘɪꜱᴏᴅᴇꜱ ᴘʀᴏᴄᴇꜱꜱᴇᴅ:</b> <code>{processed_eps}</code>\n"
        f"📡 <b>ᴏɴɢᴏɪɴɢ ᴀᴜᴛᴏ-ᴅᴏᴡɴʟᴏᴀᴅ:</b> {'✅ ᴏɴ' if ongoing_enabled else '❌ ᴏғғ'}"
        f"{storage_info}"
        f"{sys_info}"
        f"{specs}</blockquote>"
    )

    await sts.edit_text(text, parse_mode=ParseMode.HTML)

@Client.on_message(filters.private & filters.command("ping"))
async def handle_ping(client: Client, message):
    start_t = time.time()
    msg = await message.reply("<b>ᴘᴏɴɢ...</b>", parse_mode=ParseMode.HTML)
    end_t = time.time()

    ping = (end_t - start_t) * 1000
    await msg.edit_text(f"<b>ᴘᴏɴɢ!</b> <code>{ping:.3f} ᴍꜱ</code>", parse_mode=ParseMode.HTML)


@Client.on_message(filters.private & filters.command(["mongodb", "mongostatus", "mgdb"]))
async def handle_mongodb(client: Client, message):
    """Check MongoDB status (admin only)."""
    is_admin = await db.is_admin(message.from_user.id)
    if message.from_user.id != OWNER_ID and not is_admin:
        return await message.reply("<blockquote>❌ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ɪꜱ ғᴏʀ ᴀᴅᴍɪɴɪꜱᴛʀᴀᴛᴏʀꜱ ᴏɴʟʏ.</blockquote>", parse_mode=ParseMode.HTML)

    sts = await message.reply("<blockquote>🍃 <b>ᴄʜᴇᴄᴋɪɴɢ ᴍᴏɴɢᴏᴅʙ...</b></blockquote>", parse_mode=ParseMode.HTML)
    status = await db.get_mongo_status()

    def fmt(b):
        if b is None:
            return "—"
        if b < 1024 * 1024:
            return f"{b / 1024:.1f} KB"
        if b < 1024 * 1024 * 1024:
            return f"{b / (1024 * 1024):.2f} MB"
        return f"{b / (1024 * 1024 * 1024):.2f} GB"

    if not status.get("connected"):
        text = (
            "<blockquote>🍃 <b>ᴍᴏɴɢᴏᴅʙ sᴛᴀᴛᴜs</b>\n\n"
            "<b>✦ sᴛᴀᴛᴜs</b> › ❌ <b>ᴅɪsᴄᴏɴɴᴇᴄᴛᴇᴅ / ɴᴏᴛ ᴄᴏɴғɪɢᴜʀᴇᴅ</b>\n"
            f"<b>✦ ᴅᴇᴛᴀɪʟ</b> › <code>{status.get('error', 'unknown')}</code></blockquote>"
        )
        return await sts.edit_text(text, parse_mode=ParseMode.HTML)

    uptime_h = status.get("uptime")
    uptime_txt = f"{uptime_h / 3600:.1f}h" if isinstance(uptime_h, (int, float)) else "—"

    text = (
        "<blockquote expandable>🍃 <b>ᴍᴏɴɢᴏᴅʙ sᴛᴀᴛᴜs</b>\n\n"
        f"<b>✦ sᴛᴀᴛᴜs</b> › ✅ <b>ᴄᴏɴɴᴇᴄᴛᴇᴅ</b>\n"
        f"<b>✦ ᴘɪɴɢ</b> › <code>{status.get('ping_ms', 0):.1f} ᴍs</code>\n"
        f"<b>✦ ᴠᴇʀsɪᴏɴ</b> › <code>{status.get('version') or '—'}</code>\n"
        f"<b>✦ ᴜᴘᴛɪᴍᴇ</b> › <code>{uptime_txt}</code>\n"
        f"<b>✦ ᴄᴏɴɴᴇᴄᴛɪᴏɴs</b> › <code>{status.get('connections') if status.get('connections') is not None else '—'}</code>\n\n"
        f"<b>✦ ᴄᴏʟʟᴇᴄᴛɪᴏɴs</b> › <code>{status.get('collections_count', 0)}</code>\n"
        f"<b>✦ ᴏʙᴊᴇᴄᴛs</b> › <code>{status.get('objects') if status.get('objects') is not None else '—'}</code>\n"
        f"<b>✦ ɪɴᴅᴇxᴇs</b> › <code>{status.get('indexes') if status.get('indexes') is not None else '—'}</code>\n"
        f"<b>✦ ᴅᴀᴛᴀ</b> › <code>{fmt(status.get('data_size'))}</code>\n"
        f"<b>✦ sᴛᴏʀᴀɢᴇ</b> › <code>{fmt(status.get('storage_size'))}</code>\n"
        f"<b>✦ ɪɴᴅᴇx</b> › <code>{fmt(status.get('index_size'))}</code>\n"
        f"<b>✦ ᴛᴏᴛᴀʟ</b> › <code>{fmt(status.get('total_size'))}</code></blockquote>"
    )
    if status.get("collections"):
        text += f"\n\n<code>{status.get('collections')}</code>"

    await sts.edit_text(text, parse_mode=ParseMode.HTML)


@Client.on_message(filters.private & filters.command("restart"))
async def handle_restart(client: Client, message):
    is_admin = await db.is_admin(message.from_user.id)
    if message.from_user.id != OWNER_ID and not is_admin:
        return await message.reply("<blockquote>❌ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ɪꜱ ᴏɴʟʏ ꜰᴏʀ ᴀᴅᴍɪɴꜱ ᴏʀ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ.</blockquote>", parse_mode=ParseMode.HTML)

    msg = await message.reply("<b>🔄 ʀᴇꜱᴛᴀʀᴛɪɴɢ ʙᴏᴛ...</b>", parse_mode=ParseMode.HTML)

    # Save the restart message info to DB so it can be updated after restart
    await db.set_user_setting(OWNER_ID, "restart_msg_id", msg.id)
    await db.set_user_setting(OWNER_ID, "restart_chat_id", msg.chat.id)

    # Restart the current process
    os.execl(sys.executable, sys.executable, "-m", "cantarella")

@Client.on_message(filters.private & filters.command("broadcast") & admin & filters.reply)
async def handle_broadcast(client: Client, message):
    broadcast_msg = message.reply_to_message
    sts = await message.reply("<blockquote>🚀 <b>ꜱᴛᴀʀᴛɪɴɢ ʙʀᴏᴀᴅᴄᴀꜱᴛ...</b></blockquote>", parse_mode=ParseMode.HTML)

    users = await db.get_all_users()
    count = 0
    success = 0
    failed = 0

    async for user in users:
        user_id = user["_id"]
        try:
            await broadcast_msg.copy(user_id)
            success += 1
        except Exception:
            failed += 1

        count += 1
        if count % 20 == 0:
            try:
                await sts.edit_text(f"<blockquote>🚀 <b>ʙʀᴏᴀᴅᴄᴀꜱᴛɪɴɢ...</b>\n\n✅ ꜱᴜᴄᴄᴇꜱꜱ: {success}\n❌ ғᴀɪʟᴇᴅ: {failed}</blockquote>", parse_mode=ParseMode.HTML)
            except:
                pass

        await asyncio.sleep(0.5) # Avoid flood limits

    await sts.edit_text(f"<blockquote>✅ <b>ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ!</b>\n\n👥 ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ: {success + failed}\n✨ ꜱᴜᴄᴄᴇꜱꜱ: {success}\n💀 ғᴀɪʟᴇᴅ: {failed}</blockquote>", parse_mode=ParseMode.HTML)

@Client.on_message(filters.private & filters.command("broadcast") & admin & ~filters.reply)
async def handle_broadcast_no_reply(client: Client, message):
    await message.reply("<blockquote>❌ ᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇꜱꜱᴀɢᴇ ᴛᴏ ʙʀᴏᴀᴅᴄᴀꜱᴛ ɪᴛ.</blockquote>", parse_mode=ParseMode.HTML)
