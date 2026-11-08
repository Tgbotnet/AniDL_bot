#@cantarellabots
from pyrogram.enums import ParseMode
from pyrogram import Client
from queue import Queue, Empty
from threading import Thread
import asyncio
import os
import time
from cantarella.scraper.cantarellatv import cantarellatvDownloader
from cantarella.core.utils import is_video_file
from cantarella.core.images import get_random_image
from cantarella.core.database import db
from config import LOG_CHANNEL


async def schedule_deletion(client: Client, chat_id: int, message_id: int, delay: int, notify_msg_id: int = None):
    """Wait for 'delay' seconds, then delete the specified message(s)."""
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id, message_id)
        if notify_msg_id:
            await client.delete_messages(chat_id, notify_msg_id)
    except Exception:
        pass


# Global semaphores to limit concurrent tasks and prevent resource conflicts
download_semaphore = asyncio.Semaphore(1)
upload_semaphore = asyncio.Semaphore(1)


def _make_progress_bar(percent: float, length: int = 10) -> str:
    """Generate a visual progress bar string."""
    filled = int(length * percent / 100)
    empty = length - filled
    bar = "●" * filled + "○" * empty
    return f"[{bar}] {percent:.1f}%"


async def _handle_download(client: Client, message, url, status_msg, is_playlist=False, quality="auto", chat_id=None, name_override=None, season_override=None, ep_num_override=None):
    if chat_id is None:
        chat_id = message.chat.id if message else status_msg.chat.id

    # The user's original chat for user-side progress
    user_chat_id = message.chat.id if message else (status_msg.chat.id if status_msg else None)

    # Progress is always reported in LOG_CHANNEL if set, otherwise we disable progress updates to avoid spamming target chats
    progress_chat_id = int(LOG_CHANNEL) if LOG_CHANNEL else None

    # If the request didn't come from LOG_CHANNEL and LOG_CHANNEL is valid, try to create a new status message there or reuse
    if progress_chat_id and getattr(status_msg, "chat", None) and getattr(status_msg.chat, "id", None) != progress_chat_id:
        try:
            from pyrogram.errors import FloodWait
            new_status_msg = await client.send_message(progress_chat_id, f"<blockquote>🔄 ꜱᴛᴀʀᴛɪɴɢ ᴘʀᴏᴄᴇꜱꜱ ғᴏʀ: {url}</blockquote>", parse_mode=ParseMode.HTML)
            status_msg = new_status_msg
            await asyncio.sleep(1)
        except FloodWait as e:
            print(f"FloodWait on progress message: {e}. Suppressing.")
            progress_chat_id = None # Disable progress updates for this run if we hit floodwait
            pass
        except Exception as e:
            print(f"Failed to send status to LOG_CHANNEL: {e}")
            progress_chat_id = None
            pass

    # ── Create a user-side progress message ──
    user_progress_msg = None

    # Inform the user if the task is waiting in the queue
    if download_semaphore.locked():
        if progress_chat_id and hasattr(status_msg, "id"):
            try:
                await client.edit_message_text(progress_chat_id, status_msg.id, f"<blockquote>⏳ **ᴡᴀɪᴛɪɴɢ ɪɴ ǫᴜᴇᴜᴇ...**\nᴀɴɪᴍᴇ: {name_override or url}\nǫᴜᴀʟɪᴛʏ: {quality}</blockquote>", parse_mode=ParseMode.HTML)
            except Exception:
                pass

    async with download_semaphore:
        if progress_chat_id and hasattr(status_msg, "id"):
            try:
                await client.edit_message_text(progress_chat_id, status_msg.id, f"<blockquote>🔄 **ᴘʀᴇᴘᴀʀɪɴɢ ꜱᴛᴀʀᴛᴇᴅ...**\nᴀɴɪᴍᴇ: {name_override or url}</blockquote>", parse_mode=ParseMode.HTML)
            except Exception:
                pass
        return await __handle_download_internal(client, message, url, status_msg, is_playlist, quality, chat_id, progress_chat_id, name_override, season_override, ep_num_override, user_chat_id, user_progress_msg)


async def __handle_download_internal(client: Client, message, url, status_msg, is_playlist, quality, chat_id, progress_chat_id, name_override, season_override, ep_num_override, user_chat_id, user_progress_msg):
    progress_q = Queue()
    upload_q = Queue()
    downloader = cantarellatvDownloader(progress_queue=progress_q)

    uploaded_messages = []
    active_uploads = [0]
    error = [None]

    def download_target():
        if is_playlist and quality != "all":
            # Strict one-by-one: download ep -> upload -> delete -> next ep.
            try:
                entries = downloader.list_episodes(url)
            except Exception:
                entries = []
            for entry in entries:
                downloader.download_episode(entry.get("url", url), quality=quality,
                                              name_override=name_override, season_override=season_override,
                                              ep_num_override=ep_num_override)
                # Wait for the monitor to finish uploading + deleting this
                # episode's file before starting the next download.
                while not (active_uploads[0] == 0 and progress_q.empty() and upload_q.empty()):
                    time.sleep(0.5)
        else:
            downloader.download_episode(url, quality=quality, name_override=name_override, season_override=season_override, ep_num_override=ep_num_override)

    thread = Thread(target=download_target)
    thread.start()

    async def do_upload(filename, title):
        succeeded = False
        last_up_time = [time.time()]
        last_up_size = [0]

        def up_cb(current, total):
            now = time.time()
            diff_time = now - last_up_time[0]
            if diff_time >= 2:
                diff_size = current - last_up_size[0]
                speed_mb = (diff_size / diff_time / 1024 / 1024)
                percent = (current / total) * 100

                def format_size(b):
                    for unit in ['B', 'KB', 'MB', 'GB']:
                        if b < 1024: return f"{b:.1f} {unit}"
                        b /= 1024
                    return f"{b:.1f} TB"

                upload_q.put({
                    'uploading': {
                        'percent': round(percent, 1),
                        'speed': f"{speed_mb:.1f} MB/s",
                        'title': title,
                        'current': format_size(current),
                        'total': format_size(total)
                    }
                })
                last_up_time[0] = now
                last_up_size[0] = current

        try:
            async with upload_semaphore:
                # Add explicit file_name so Telegram does not infer weird numeric names
                ext = os.path.splitext(filename)[1] or ".mkv"
                actual_file_name = f"{title}{ext}"

                # Try to use CAPTION config format if possible
                file_caption = ""
                try:
                    from config import CAPTION
                    file_caption = CAPTION.replace("{FORMAT}", title)
                except Exception:
                    file_caption = title

                # No thumbnail: thumb.jpg (1536x1024) exceeds Telegram's
                # 320x320 / 200KB limit and makes WzGram's send_document
                # error out / appear to hang after the file progress.
                print(f"[upload] starting {actual_file_name} -> {chat_id}", flush=True)
                up_msg = await client.send_document(
                    chat_id,
                    document=filename,
                    file_name=actual_file_name,
                    caption=file_caption,
                    progress=up_cb
                )
                print(f"[upload] done {actual_file_name} msg={up_msg.id if up_msg else 'null'}", flush=True)
                uploaded_messages.append(up_msg)
                succeeded = True
                upload_q.put({'uploaded': True})

                # --- Auto-Delete Logic for User PM ---
                # Check if this is a private chat (user PM) or if we should delete in the target chat too
                async def check_and_schedule_autodel(target_id):
                    try:
                        chat = await client.get_chat(target_id)
                        if chat.type == "private":
                            autodel_time = await db.get_user_setting(0, "autodel_time", 0)
                            if autodel_time > 0:
                                mins = autodel_time // 60
                                notify_msg = await client.send_message(
                                    target_id,
                                    f"<blockquote>🗑️ <b>ᴛʜɪꜱ ғɪʟᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ᴀғᴛᴇʀ {mins} ᴍɪɴ ({autodel_time}ꜱ).</b>\n"
                                    "<i>ᴍᴀᴋᴇ ꜱᴜʀᴇ ᴛᴏ ꜱᴀᴠᴇ ɪᴛ ɪɴ ʏᴏᴜʀ 'ꜱᴀᴠᴇᴅ ᴍᴇꜱꜱᴀɢᴇꜱ' ɪғ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴋᴇᴇᴘ ɪᴛ!</i></blockquote>",
                                    reply_to_message_id=up_msg.id,
                                    parse_mode=ParseMode.HTML
                                )
                                asyncio.create_task(schedule_deletion(client, target_id, up_msg.id, autodel_time, notify_msg.id))
                    except Exception:
                        pass

                await check_and_schedule_autodel(chat_id)
                if user_chat_id and user_chat_id != chat_id:
                    await check_and_schedule_autodel(user_chat_id)

        except Exception as e:

            upload_q.put({'upload_error': str(e)})
            print(f"[upload] failed {filename}: {e}", flush=True)
            try:
                await client.send_message(progress_chat_id, f"<blockquote>❌ ᴜᴘʟᴏᴀᴅ ғᴀɪʟᴇᴅ ғᴏʀ {title}: {str(e)}</blockquote>", parse_mode=ParseMode.HTML)
            except Exception:
                pass
        finally:
            active_uploads[0] -= 1
            # Delete only after a successful upload so failed files stay for
            # inspection/retry and strict one-by-one batches can proceed.
            if succeeded:
                try:
                    os.unlink(filename)
                    print(f"[upload] deleted {filename} after successful upload", flush=True)
                except FileNotFoundError:
                    pass
                except Exception as exc:
                    print(f"[upload] could not delete {filename}: {exc}", flush=True)
            else:
                print(f"[upload] keeping {filename} (upload did not succeed)", flush=True)

    async def monitor():
        current_episode_title = "Unknown"
        last_text = ""
        last_edit_time = 0
        last_user_edit_time = 0
        last_user_text = ""
        dl_status = {'sub': None, 'dub': None}

        while thread.is_alive() or not progress_q.empty() or not upload_q.empty() or active_uploads[0] > 0:
            text = None

            while not progress_q.empty():
                try:
                    info = progress_q.get_nowait()
                    if 'error' in info:
                        error[0] = info['error']
                        if active_uploads[0] > 0:
                            text = f"<blockquote>⚠️ **ᴅᴏᴡɴʟᴏᴀᴅ ᴇʀʀᴏʀ:** {info['error']}\n📤 ᴡᴀɪᴛɪɴɢ ғᴏʀ {active_uploads[0]} ᴜᴘʟᴏᴀᴅ(ꜱ) ᴛᴏ ғɪɴɪꜱʜ...</blockquote>"
                        continue
                    if 'status' in info:
                        text = info['status']
                    elif 'finished' in info:
                        dl_status = {'sub': None, 'dub': None}
                        filename = info['filename']
                        title = info['title']
                        current_episode_title = title
                        # Upload anything that was actually produced (Re:Anime
                        # falls back to .ts without ffmpeg — still valid).
                        uploadable = False
                        try:
                            uploadable = os.path.exists(filename) and os.path.getsize(filename) > 0
                        except Exception:
                            uploadable = is_video_file(filename)
                        if uploadable:
                            active_uploads[0] += 1
                            text = f"<blockquote>📤 **ᴅᴏᴡɴʟᴏᴀᴅ ᴄᴏᴍᴘʟᴇᴛᴇ!**\nꜱᴛᴀʀᴛɪɴɢ ᴜᴘʟᴏᴀᴅ: {title}...</blockquote>"
                            task = asyncio.create_task(do_upload(filename, title))
                            task.set_name(f"upload_{title}")
                    elif 'percent' in info:
                        dl_type = info.get('type', 'sub')
                        dl_status[dl_type] = info
                        current_episode_title = info.get('title', current_episode_title)

                        primary = dl_status['sub'] or dl_status['dub']
                        if primary:
                            try:
                                pct = float(str(primary['percent']).replace('%', ''))
                            except:
                                pct = 0

                            from config import PROGRESS_BAR
                            bar_str = PROGRESS_BAR.format(
                                bar=_make_progress_bar(pct),
                                title=current_episode_title,
                                speed=primary['speed'],
                                current=primary['downloaded'],
                                total=primary['total']
                            )

                            # Update LOG_CHANNEL to use exactly the same visual progress
                            text = (
                                f"<blockquote>📥 <b><i>ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ...</i></b>\n"
                                f"{bar_str}</blockquote>"
                            )
                except Empty:
                    break

            # Only break on error if there are NO active uploads left
            if error[0] and active_uploads[0] <= 0 and progress_q.empty():
                break

            while not upload_q.empty():
                try:
                    info = upload_q.get_nowait()
                    if 'uploaded' in info:
                        text = f"<blockquote>📤 **ᴜᴘʟᴏᴀᴅᴇᴅ {len(uploaded_messages)} ᴇᴘɪꜱᴏᴅᴇ(ꜱ)**\nᴡᴀɪᴛɪɴɢ ғᴏʀ ɴᴇxᴛ...</blockquote>"
                    elif 'uploading' in info:
                        up = info['uploading']
                        from config import PROGRESS_BAR
                        bar_str = PROGRESS_BAR.format(
                            bar=_make_progress_bar(up['percent']),
                            title=up['title'],
                            speed=up['speed'],
                            current=up.get('current', '?'),
                            total=up.get('total', '?')
                        )

                        text = (
                            f"<blockquote>📤 <b><i>ᴜᴘʟᴏᴀᴅɪɴɢ...</i></b>\n"
                            f"{bar_str}</blockquote>"
                        )
                    elif 'upload_error' in info:
                        text = f"<blockquote>⚠️ ᴜᴘʟᴏᴀᴅ ᴇʀʀᴏʀ: {info['upload_error']}</blockquote>"
                except Empty:
                    break

            now = time.time()

            # Update LOG_CHANNEL

            if progress_chat_id and hasattr(status_msg, "id") and text and text != last_text and (now - last_edit_time) > 2.5:
                try:
                    await client.edit_message_text(progress_chat_id, status_msg.id, text, parse_mode=ParseMode.HTML)
                    last_text = text
                    last_edit_time = now
                except Exception:
                    pass

            await asyncio.sleep(0.5)
        thread.join()

    await monitor()

    # ── Final status updates ──

    if progress_chat_id and hasattr(status_msg, "id"):
        if uploaded_messages:
            unit = 'episode(s)' if is_playlist else 'file(s)'
            unit_sc = unit
            suffix = ""
            if error[0]:
                suffix = f"\n⚠️ ɴᴏᴛᴇ: ᴅᴏᴡɴʟᴏᴀᴅ ʜᴀᴅ ᴇʀʀᴏʀꜱ ʙᴜᴛ {len(uploaded_messages)} {unit_sc} ᴡᴇʀᴇ ꜱᴀᴠᴇᴅ."
            try:
                await client.edit_message_text(
                    progress_chat_id, status_msg.id,
                    f"<blockquote>✅ **ᴅᴏᴡɴʟᴏᴀᴅ & ᴜᴘʟᴏᴀᴅ ᴄᴏᴍᴘʟᴇᴛᴇ!**\nᴜᴘʟᴏᴀᴅᴇᴅ {len(uploaded_messages)} {unit_sc} ꜱᴜᴄᴄᴇꜱꜱғᴜʟʟʏ.{suffix}</blockquote>",
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                pass
        elif error[0]:
            try:
                await client.edit_message_text(progress_chat_id, status_msg.id, f"<blockquote>❌ ᴅᴏᴡɴʟᴏᴀᴅ ᴇʀʀᴏʀ: {error[0]}</blockquote>", parse_mode=ParseMode.HTML)
            except Exception:
                pass
        else:
            try:
                await client.edit_message_text(progress_chat_id, status_msg.id, "<blockquote>❌ ɴᴏ ғɪʟᴇꜱ ᴡᴇʀᴇ ꜱᴜᴄᴄᴇꜱꜱғᴜʟʟʏ ᴜᴘʟᴏᴀᴅᴇᴅ.</blockquote>", parse_mode=ParseMode.HTML)
            except Exception:
                pass

    return uploaded_messages, status_msg
