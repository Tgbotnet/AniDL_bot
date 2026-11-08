#@cantarellabots
from pyrogram import Client
from pyrogram.types import BotCommand

async def set_bot_commands(client: Client):
    """Automatically setup bot commands on startup."""
    commands = [
        BotCommand("start", "🚀 Sᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ"),
        BotCommand("favorites", "❤ Vɪᴇᴡ ʏᴏᴜʀ ғᴀᴠᴏʀɪᴛᴇ ᴀɴɪᴍᴇ (Aᴅᴍɪɴ)"),
        BotCommand("ongoing", "📆 Vɪᴇᴡ ᴛᴏᴅᴀʏ's ᴀɴɪᴍᴇ sᴄʜᴇᴅᴜʟᴇ"),
        BotCommand("autodel", "🕒 Sᴇᴛ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ᴛɪᴍᴇ (Aᴅᴍɪɴ)"),
        BotCommand("manage", "⚙️ Mᴀɴᴀɢᴇ ʙᴏᴛ sᴇᴛᴛɪɴɢs (Aᴅᴍɪɴ)"),
        BotCommand("stats", "📊 Vɪᴇᴡ ʙᴏᴛ & sʏsᴛᴇᴍ sᴛᴀᴛɪsᴛɪᴄs (Aᴅᴍɪɴ)"),
        BotCommand("maplist", "📋 Vɪᴇᴡ ᴀɴɪᴍᴇ ᴍᴀᴘᴘɪɴɢs (Aᴅᴍɪɴ)"),
        BotCommand("setmap", "📍 Sᴇᴛ ᴀɴɪᴍᴇ ᴍᴀᴘᴘɪɴɢ (Aᴅᴍɪɴ)"),
        BotCommand("unmap", "❌ Rᴇᴍᴏᴠᴇ ᴀɴɪᴍᴇ ᴍᴀᴘᴘɪɴɢ (Aᴅᴍɪɴ)"),
        BotCommand("admins", "🛡️ Vɪᴇᴡ ʙᴏᴛ ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀs (Aᴅᴍɪɴ)"),
        BotCommand("users", "👥 Vɪᴇᴡ ᴛᴏᴛᴀʟ ᴜsᴇʀs (Aᴅᴍɪɴ)"),
        BotCommand("ping", "🏓 Cʜᴇᴄᴋ ʙᴏᴛ ʟᴀᴛᴇɴᴄʏ"),
        BotCommand("restart", "🔄 Rᴇsᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ (Aᴅᴍɪɴ)"),
        BotCommand("broadcast", "📡 Bʀᴏᴀᴅᴄᴀsᴛ ᴀ ᴍᴇssᴀɢᴇ (Aᴅᴍɪɴ)"),
    ]
    try:
        await client.set_bot_commands(commands)
        print("Bot commands setup successfully!")
    except Exception as e:
        print(f"Failed to setup bot commands: {e}")
