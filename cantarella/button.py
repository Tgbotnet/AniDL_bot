#@cantarellabots
from pyrogram.types import InlineKeyboardButton as PyroButton
from pyrogram.enums import ButtonStyle

class Button(PyroButton):
    def __init__(self, text, callback_data=None, url=None, web_app=None,
                 login_url=None, user_id=None, switch_inline_query=None,
                 switch_inline_query_current_chat=None, callback_game=None,
                 requires_password=None, pay=None, copy_text=None,
                 icon_custom_emoji_id=None, style=None):
        if style is None:
            # Semantic coloring based on button text
            lower_text = text.lower()
            if any(x in lower_text for x in ["close", "cancel", "delete", "ban", "❌", "✖️", "back", "⬅️", "del", "remove", "➖"]):
                style = ButtonStyle.DANGER
            elif any(x in lower_text for x in ["done", "download", "✅", "📥", "success", "add", "➕", "start"]):
                # Removed "on" from success because "Random Option" contains "on"
                style = ButtonStyle.SUCCESS
            else:
                style = ButtonStyle.PRIMARY

        super().__init__(text, callback_data=callback_data, url=url, web_app=web_app,
                         login_url=login_url, user_id=user_id, switch_inline_query=switch_inline_query,
                         switch_inline_query_current_chat=switch_inline_query_current_chat,
                         callback_game=callback_game, requires_password=requires_password,
                         pay=pay, copy_text=copy_text, icon_custom_emoji_id=icon_custom_emoji_id,
                         style=style)
