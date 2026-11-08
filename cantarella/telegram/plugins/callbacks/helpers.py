#@cantarellabots
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant
from cantarella.core.database import db
from config import *
import logging
from datetime import datetime, timedelta
from pyrogram.types import InlineKeyboardMarkup
from cantarella.button import Button as InlineKeyboardButton

logger = logging.getLogger(__name__)

async def check_fsub(client, user_id):
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

    channel_ids = await db.show_channels()
    if not channel_ids:
        return True
    if user_id == OWNER_ID:
        return True
    for cid in channel_ids:
        if not await is_sub(client, user_id, cid):
            mode = await db.get_channel_mode(cid)
            if mode == "on":
                import asyncio
                await asyncio.sleep(2)
                if await is_sub(client, user_id, cid):
                    continue
            return False
    return True

async def send_fsub_prompt(client, message):
    user_id = message.chat.id
    buttons = []

    try:
        all_channels = await db.show_channels()
        for chat_id in all_channels:
            try:
                data = await client.get_chat(chat_id)
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

            except Exception as e:
                logger.error(f"Error with chat {chat_id}: {e}")

        try:
            buttons.append([
                InlineKeyboardButton(
                    text='• Jᴏɪɴᴇᴅ •',
                    url=f"https://t.me/{BOT_USERNAME}?start=start"
                )
            ])
        except IndexError:
            pass

        text = "<b>Yᴏᴜ Bᴀᴋᴋᴀᴀ...!! \n\n<blockquote>Jᴏɪɴ ᴍʏ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴍʏ ᴏᴛʜᴇʀᴡɪsᴇ Yᴏᴜ ᴀʀᴇ ɪɴ ʙɪɢ sʜɪᴛ...!!</blockquote></b>"

        await message.reply_photo(
            photo=FSUB_PIC,
            caption=text,
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    except Exception as e:
        logger.error(f"Error in send_fsub_prompt: {e}")
