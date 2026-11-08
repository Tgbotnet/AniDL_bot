#@cantarellabots
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InputMediaPhoto
from cantarella.button import Button as InlineKeyboardButton
from pyrogram.enums import ParseMode
from config import *
from Script import Dead
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Start / About / Help  (navigation callbacks)
# ─────────────────────────────────────────────

from cantarella.core.database import db

@Client.on_callback_query(filters.regex("^start$"))
async def cb_start(client: Client, callback_query):
    buttons = []
    is_admin = await db.is_admin(callback_query.from_user.id)
    if is_admin or callback_query.from_user.id == OWNER_ID:
        buttons.append([
            InlineKeyboardButton("⚙️ ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ", callback_data="admin_panel"),
            InlineKeyboardButton("🔄 ᴏɴɢᴏɪɴɢ", callback_data="toggle_ongoing")
        ])

    if is_admin or callback_query.from_user.id == OWNER_ID:
        buttons.append([
            InlineKeyboardButton("❤ ғᴀᴠᴏʀɪᴛᴇꜱ", callback_data="favorites")
        ])

    buttons.append([
        InlineKeyboardButton("✦ ᴀʙᴏᴜᴛ", callback_data="about"),
        InlineKeyboardButton("ʜᴇʟᴘ ✦",  callback_data="help")
    ])

    inline_buttons = InlineKeyboardMarkup(buttons)
    try:
        await callback_query.edit_message_media(
            InputMediaPhoto(
                START_PIC,
                Dead.START_MSG.format(
                    first    = callback_query.from_user.first_name,
                    last     = callback_query.from_user.last_name or "",
                    username = f"@{callback_query.from_user.username}" if callback_query.from_user.username else "ɴᴏɴᴇ",
                    mention  = callback_query.from_user.mention,
                    id       = callback_query.from_user.id
                )
            ),
            reply_markup=inline_buttons
        )
    except Exception as e:
        logger.error(f"ᴇʀʀᴏʀ ꜱᴇɴᴅɪɴɢ ꜱᴛᴀʀᴛ ᴘʜᴏᴛᴏ: {e}")
        await callback_query.edit_message_text(
            Dead.START_MSG.format(
                first    = callback_query.from_user.first_name,
                last     = callback_query.from_user.last_name or "",
                username = f"@{callback_query.from_user.username}" if callback_query.from_user.username else "ɴᴏɴᴇ",
                mention  = callback_query.from_user.mention,
                id       = callback_query.from_user.id
            ),
            reply_markup=inline_buttons,
            parse_mode=ParseMode.HTML
        )


@Client.on_callback_query(filters.regex("^about$"))
async def cb_about(client: Client, callback_query):
    await callback_query.edit_message_media(
        InputMediaPhoto("https://files.catbox.moe/is7q4q.jpg", Dead.ABOUT_TXT),
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⬅️ ʙᴀᴄᴋ",  callback_data="start"),
                InlineKeyboardButton("❌ ᴄʟᴏꜱᴇ", callback_data="close")
            ]
        ])
    )


@Client.on_callback_query(filters.regex("^help$"))
async def cb_help(client: Client, callback_query):
    await callback_query.edit_message_media(
        InputMediaPhoto(
            "https://envs.sh/Wdj.jpg",
            Dead.HELP_TXT.format(
                first    = callback_query.from_user.first_name,
                last     = callback_query.from_user.last_name or "",
                username = f"@{callback_query.from_user.username}" if callback_query.from_user.username else "ɴᴏɴᴇ",
                mention  = callback_query.from_user.mention,
                id       = callback_query.from_user.id
            )
        ),
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⬅️ ʙᴀᴄᴋ",  callback_data="start"),
                InlineKeyboardButton("❌ ᴄʟᴏꜱᴇ", callback_data="close")
            ]
        ])
    )

# ─────────────────────────────────────────────
#  Cancel / close
# ─────────────────────────────────────────────

@Client.on_callback_query(filters.regex("^(cancel|close)$"))
async def on_cancel_or_close(client, callback_query):
    try:
        await callback_query.message.delete()
    except:
        pass
    try:
        await callback_query.message.reply_to_message.delete()
    except:
        pass
