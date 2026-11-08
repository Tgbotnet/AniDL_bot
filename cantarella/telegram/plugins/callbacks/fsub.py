#@cantarellabots
from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatMemberStatus
from pyrogram.types import InlineKeyboardMarkup, ChatMemberUpdated
from cantarella.button import Button as InlineKeyboardButton
from config import *
from cantarella.core.database import db
from .admin import admin

# ─────────────────────────────────────────────
#  Force-sub mode callbacks  (was /fsub_mode)
# ─────────────────────────────────────────────

@Client.on_callback_query(filters.regex("^fsub_mode$") & admin)
async def cb_fsub_mode(client: Client, callback_query):
    channels = await db.show_channels()
    if not channels:
        return await callback_query.answer("❌ ɴᴏ ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟꜱ ꜰᴏᴜɴᴅ.", show_alert=True)

    buttons = []
    for ch_id in channels:
        try:
            chat   = await client.get_chat(ch_id)
            mode   = await db.get_channel_mode(ch_id)
            status = "🟢" if mode == "on" else "🔴"
            buttons.append([InlineKeyboardButton(f"{status} {chat.title}", callback_data=f"rfs_ch_{ch_id}")])
        except:
            buttons.append([InlineKeyboardButton(f"⚠️ {ch_id} (ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ)", callback_data=f"rfs_ch_{ch_id}")])

    buttons.append([InlineKeyboardButton("ᴄʟᴏꜱᴇ ✖️", callback_data="close")])
    await callback_query.edit_message_text(
        "<b>⚡ ꜱᴇʟᴇᴄᴛ ᴀ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴛᴏɢɢʟᴇ ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴍᴏᴅᴇ:</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex("^rfs_ch_"))
async def cb_rfs_channel(client: Client, callback_query):
    cid = int(callback_query.data.split("_")[2])
    try:
        chat     = await client.get_chat(cid)
        mode     = await db.get_channel_mode(cid)
        status   = "ON" if mode == "on" else "OFF"
        new_mode = "off" if mode == "on" else "on"
        buttons  = [
            [InlineKeyboardButton(
                f"ꜰᴏʀᴄᴇꜱᴜʙ ᴍᴏᴅᴇ {'OFF' if mode == 'on' else 'ON'}",
                callback_data=f"rfs_toggle_{cid}_{new_mode}"
            )],
            [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="fsub_back")]
        ]
        await callback_query.message.edit_text(
            f"<b>ᴄʜᴀɴɴᴇʟ:</b> {chat.title}\n<b>ᴄᴜʀʀᴇɴᴛ ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴍᴏᴅᴇ:</b> {status}",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
    except Exception:
        await callback_query.answer("ꜰᴀɪʟᴇᴅ ᴛᴏ ꜰᴇᴛᴄʜ ᴄʜᴀɴɴᴇʟ ɪɴꜰᴏ", show_alert=True)


@Client.on_callback_query(filters.regex("^rfs_toggle_"))
async def cb_rfs_toggle(client: Client, callback_query):
    parts    = callback_query.data.split("_")[2:]
    cid      = int(parts[0])
    action   = parts[1]
    mode     = "on" if action == "on" else "off"

    await db.set_channel_mode(cid, mode)
    await callback_query.answer(f"ꜰᴏʀᴄᴇ-ꜱᴜʙ ꜱᴇᴛ ᴛᴏ {'ON' if mode == 'on' else 'OFF'}")

    chat     = await client.get_chat(cid)
    status   = "ON" if mode == "on" else "OFF"
    new_mode = "off" if mode == "on" else "on"
    buttons  = [
        [InlineKeyboardButton(
            f"ꜰᴏʀᴄᴇꜱᴜʙ ᴍᴏᴅᴇ {'OFF' if mode == 'on' else 'ON'}",
            callback_data=f"rfs_toggle_{cid}_{new_mode}"
        )],
        [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="fsub_back")]
    ]
    await callback_query.message.edit_text(
        f"<b>ᴄʜᴀɴɴᴇʟ:</b> {chat.title}\n<b>ᴄᴜʀʀᴇɴᴛ ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴍᴏᴅᴇ:</b> {status}",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


@Client.on_callback_query(filters.regex("^fsub_back$"))
async def cb_fsub_back(client: Client, callback_query):
    channels = await db.show_channels()
    buttons  = []
    for cid in channels:
        try:
            chat   = await client.get_chat(cid)
            mode   = await db.get_channel_mode(cid)
            status = "✅" if mode == "on" else "❌"
            buttons.append([InlineKeyboardButton(f"{status} {chat.title}", callback_data=f"rfs_ch_{cid}")])
        except Exception:
            continue

    if not buttons:
        buttons.append([InlineKeyboardButton("ɴᴏ ᴄʜᴀɴɴᴇʟꜱ ꜰᴏᴜɴᴅ", callback_data="no_channels")])

    await callback_query.message.edit_text(
        "ꜱᴇʟᴇᴄᴛ ᴀ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴛᴏɢɢʟᴇ ɪᴛꜱ ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴍᴏᴅᴇ:",
        reply_markup=InlineKeyboardMarkup(
            buttons + [[InlineKeyboardButton("ᴄʟᴏꜱᴇ", callback_data="close")]]
        )
    )

# ─────────────────────────────────────────────
#  Chat member events
# ─────────────────────────────────────────────

@Client.on_chat_member_updated()
async def handle_chat_members(client, chat_member_updated: ChatMemberUpdated):
    chat_id     = chat_member_updated.chat.id
    old_member  = chat_member_updated.old_chat_member

    if not old_member:
        return

    user_id = old_member.user.id

    if old_member.status == ChatMemberStatus.MEMBER:
        if await db.req_user_exist(chat_id, user_id):
            await db.del_req_user(chat_id, user_id)


@Client.on_chat_join_request()
async def handle_join_request(client, chat_join_request):
    chat_id      = chat_join_request.chat.id
    user_id      = chat_join_request.from_user.id
    all_channels = await db.show_channels()

    if chat_id in all_channels:
        if not await db.req_user_exist(chat_id, user_id):
            await db.req_user(chat_id, user_id)
