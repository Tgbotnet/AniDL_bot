#@cantarellabots
from pyrogram.enums import ParseMode, ChatMemberStatus, ChatAction
from pyrogram.errors import UserNotParticipant
from pyrogram.types import InlineKeyboardMarkup, Message
from cantarella.button import Button as InlineKeyboardButton
from pyrogram import Client
import asyncio
import logging
from functools import wraps
from datetime import datetime, timedelta

from cantarella.core.database import db
from config import OWNER_ID, FSUB_LINK_EXPIRY, FSUB_PIC, BOT_USERNAME

logger = logging.getLogger(__name__)

# Initialize chat_data_cache
chat_data_cache = {}

def check_ban(func):
    """Decorator to check if user is banned before executing function"""
    @wraps(func)
    async def wrapper(client, message, *args, **kwargs):
        user_id = message.from_user.id
        logger.debug(f"check_ban decorator called for user {user_id}")

        try:
            is_banned = await db.is_user_banned(user_id)

            if is_banned:
                logger.debug(f"User {user_id} is banned")
                keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ ʜᴇʀᴇ...!!", url="https://t.me/cantarellabots")]]
                )
                await message.reply_text(
                    "Wᴛғ ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ ғʀᴏᴍ ᴜsɪɴɢ ᴍᴇ ʙʏ ᴏᴜʀ ᴀᴅᴍɪɴ/ᴏᴡɴᴇʀ. Iғ ʏᴏᴜ ᴛʜɪɴᴋs ɪᴛ's ᴍɪsᴛᴀᴋᴇ ᴄʟɪᴄᴋ ᴏɴ ᴄᴏɴᴛᴀᴄᴛ ʜᴇʀᴇ...!!",
                    reply_markup=keyboard
                )
                return

            logger.debug(f"User {user_id} is not banned, proceeding with function call")
            return await func(client, message, *args, **kwargs)

        except Exception as e:
            logger.error(f"FATAL ERROR in check_ban: {e}", exc_info=True)
            await message.reply_text(f"An unexpected error occurred: {e}. Please contact the developer.")
            return

    return wrapper

def check_fsub(func):
    @wraps(func)
    async def wrapper(client, message, *args, **kwargs):
        user_id = message.from_user.id
        logger.debug(f"check_fsub decorator called for user {user_id}")

        async def is_sub(client, user_id, channel_id):
            try:
                member = await client.get_chat_member(channel_id, user_id)
                return member.status in {
                    ChatMemberStatus.OWNER,
                    ChatMemberStatus.ADMINISTRATOR,
                    ChatMemberStatus.MEMBER
                }
            except UserNotParticipant:
                mode = await db.get_channel_mode(channel_id) or await db.get_channel_mode_all(channel_id)
                if mode == "on":
                    exists = await db.req_user_exist(channel_id, user_id)
                    return exists
                return False
            except Exception as e:
                logger.error(f"Error in is_sub(): {e}")
                return False

        async def is_subscribed(client, user_id):
            channel_ids = await db.show_channels()
            if not channel_ids:
                return True
            if user_id == OWNER_ID:
                return True
            for cid in channel_ids:
                if not await is_sub(client, user_id, cid):
                    mode = await db.get_channel_mode(cid)
                    if mode == "on":
                        await asyncio.sleep(2)
                        if await is_sub(client, user_id, cid):
                            continue
                    return False
            return True

        try:
            is_sub_status = await is_subscribed(client, user_id)
            logger.debug(f"User {user_id} subscribed status: {is_sub_status}")

            if not is_sub_status:
                logger.debug(f"User {user_id} is not subscribed, calling not_joined.")
                return await not_joined(client, message)

            logger.debug(f"User {user_id} is subscribed, proceeding with function call.")
            return await func(client, message, *args, **kwargs)

        except Exception as e:
            logger.error(f"FATAL ERROR in check_fsub: {e}")
            await message.reply_text(f"An unexpected error occurred: {e}. Please contact the developer.")
            return
    return wrapper

async def not_joined(client: Client, message: Message):
    logger.debug(f"not_joined function called for user {message.from_user.id}")
    temp = await message.reply("<b>ᴡᴀɪᴛ ᴀ sᴇᴄ..</b>")

    # Add a check to ensure temp message exists before proceeding
    if not temp:
        logger.warning("Failed to send temporary message in not_joined")
        return

    user_id = message.from_user.id
    buttons = []
    count = 0

    try:
        all_channels = await db.show_channels()
        for chat_id in all_channels:
            await message.reply_chat_action(ChatAction.TYPING)

            is_member = False
            try:
                member = await client.get_chat_member(chat_id, user_id)
                is_member = member.status in {
                    ChatMemberStatus.OWNER,
                    ChatMemberStatus.ADMINISTRATOR,
                    ChatMemberStatus.MEMBER
                }
            except UserNotParticipant:
                is_member = False
            except Exception as e:
                is_member = False
                logger.error(f"Error checking member in not_joined: {e}")

            if not is_member:
                try:
                    if chat_id in chat_data_cache:
                        data = chat_data_cache[chat_id]
                    else:
                        data = await client.get_chat(chat_id)
                        chat_data_cache[chat_id] = data

                    name = data.title
                    mode = await db.get_channel_mode(chat_id)

                    if mode == "on" and not data.username:
                        invite = await client.create_chat_invite_link(
                            chat_id=chat_id,
                            creates_join_request=True,
                            expire_date=datetime.utcnow() + timedelta(seconds=FSUB_LINK_EXPIRY) if FSUB_LINK_EXPIRY else None
                        )
                        link = invite.invite_link
                    else:
                        if data.username:
                            link = f"https://t.me/{data.username}"
                        else:
                            invite = await client.create_chat_invite_link(
                                chat_id=chat_id,
                                expire_date=datetime.utcnow() + timedelta(seconds=FSUB_LINK_EXPIRY) if FSUB_LINK_EXPIRY else None
                            )
                            link = invite.invite_link

                    buttons.append([InlineKeyboardButton(text=name, url=link)])
                    count += 1
                    try:
                        await temp.edit(f"<b>{'! ' * count}</b>")
                    except Exception as e:
                        logger.warning(f"Failed to edit message in not_joined: {e}")

                except Exception as e:
                    logger.error(f"Error with chat {chat_id}: {e}")
                    await temp.edit(
                        f"<b>! Eʀʀᴏʀ, Cᴏɴᴛᴀᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴛᴏ sᴏʟᴠᴇ ᴛʜᴇ ɪssᴜᴇs @seishiro_obito</b>\n"
                        f"<blockquote expandable><b>Rᴇᴀsᴏɴ:</b> {e}</blockquote>"
                    )
                    return

        try:
            if len(message.command) > 1:
                buttons.append([
                    InlineKeyboardButton(
                        text='• Jᴏɪɴᴇᴅ •',
                        url=f"https://t.me/{BOT_USERNAME}?start={message.command[1]}"
                    )
                ])
            else:
                pass
        except IndexError:
            pass

        text = "<b>Yᴏᴜ Bᴀᴋᴋᴀᴀ...!! \n\n<blockquote>Jᴏɪɴ ᴍʏ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴍʏ ᴏᴛʜᴇʀᴡɪsᴇ Yᴏᴜ ᴀʀᴇ ɪɴ ʙɪɢ sʜɪᴛ...!!</blockquote></b>"

        logger.debug(f"Sending final reply photo to user {user_id}")
        await message.reply_photo(
            photo=FSUB_PIC,
            caption=text,
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    except Exception as e:
        logger.error(f"Final Error in not_joined: {e}")
        await temp.edit(
            f"<b>! Eʀʀᴏʀ, Cᴏɴᴛᴀᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴛᴏ sᴏʟᴠᴇ ᴛʜᴇ ɪssᴜᴇs @seishiro_obito</b>\n"
            f"<blockquote expandable><b>Rᴇᴀsᴏɴ:</b> {e}</blockquote>"
        )
