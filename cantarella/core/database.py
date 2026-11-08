#@cantarellabots
import motor.motor_asyncio
import logging
from datetime import datetime, date
from typing import List, Optional
from config import MONGO_URL, MONGO_NAME

logging.basicConfig(level=logging.INFO)


class Database:
    def __init__(self, uri, db_name=MONGO_NAME):
        if uri:
            self.client   = motor.motor_asyncio.AsyncIOMotorClient(uri)
            self.db       = self.client[db_name]

            # ── Collections ──────────────────────────────────────
            self.user_data                  = self.db["users"]
            self.channel_data               = self.db["channels"]
            self.admins_data                = self.db["admins"]
            self.del_timer_data             = self.db["del_timer"]
            self.ban_data                   = self.db["ban_data"]
            self.fsub_data                  = self.db["fsub"]
            self.rqst_fsub_data             = self.db["request_forcesub"]
            self.rqst_fsub_Channel_data     = self.db["request_forcesub_channel"]
            self.sequence_mode              = self.db["sequence_mode"]
            self.processed                  = self.db["processed_episodes"]
            self.settings                   = self.db["user_settings"]
            self.mapped_channels            = self.db["mapped_channels"]
            self.favorites                  = self.db["favorites"]

            # Backward-compat aliases
            self.col    = self.user_data
            self.users  = self.user_data
            self.admins = self.admins_data
        else:
            # Graceful no-op when MONGO_URL is not set
            self.client = self.db = None
            self.user_data = self.channel_data = self.admins_data = None
            self.del_timer_data = self.ban_data = self.fsub_data = None
            self.rqst_fsub_data = self.rqst_fsub_Channel_data = None
            self.sequence_mode = self.processed = self.settings = None
            self.col = self.users = self.admins = None
            logging.warning("MONGO_URL not set — database features will be disabled.")

    # ══════════════════════════════════════════════════════
    #  USER MANAGEMENT
    # ══════════════════════════════════════════════════════

    def _new_user(self, user_id: int, username: str = None) -> dict:
        return dict(
            _id=int(user_id),
            username=username.lower() if username else None,
            join_date=date.today().isoformat(),
            active=True,
            ban_status=dict(
                is_banned=False,
                ban_duration=0,
                banned_on=date.max.isoformat(),
                ban_reason="",
            )
        )

    async def add_user(self, user_id: int, username: str = None):
        """Add a new user if they don't already exist."""
        if self.user_data is None:
            return
        if not await self.is_user_exist(user_id):
            user = self._new_user(user_id, username)
            try:
                await self.user_data.insert_one(user)
                logging.info(f"ɴᴇᴡ ᴜꜱᴇʀ ᴀᴅᴅᴇᴅ: {user_id}")
            except Exception as e:
                logging.error(f"ᴇʀʀᴏʀ ᴀᴅᴅɪɴɢ ᴜꜱᴇʀ {user_id}: {e}")
        else:
            # Keep 'active' flag fresh
            await self.user_data.update_one(
                {"_id": int(user_id)},
                {"$set": {"active": True}},
                upsert=True
            )

    async def is_user_exist(self, user_id: int) -> bool:
        if self.user_data is None:
            return False
        try:
            return bool(await self.user_data.find_one({"_id": int(user_id)}))
        except Exception as e:
            logging.error(f"ᴇʀʀᴏʀ ᴄʜᴇᴄᴋɪɴɢ ᴜꜱᴇʀ {user_id}: {e}")
            return False

    async def get_all_users(self):
        if self.user_data is None:
            return iter([])
        return self.user_data.find({})

    async def total_users_count(self) -> int:
        if self.user_data is None:
            return 0
        return await self.user_data.count_documents({})

    # Alias used in broadcast
    async def get_user_count(self) -> int:
        return await self.total_users_count()

    async def get_total_users(self, active_only=False) -> int:
        if self.user_data is None:
            return 0
        query = {"active": True} if active_only else {}
        return await self.user_data.count_documents(query)

    async def delete_user(self, user_id: int):
        if self.user_data is not None:
            await self.user_data.delete_one({"_id": int(user_id)})

    # ══════════════════════════════════════════════════════
    #  BAN MANAGEMENT
    # ══════════════════════════════════════════════════════

    async def is_user_banned(self, user_id: int) -> bool:
        if self.ban_data is None:
            return False
        try:
            user = await self.ban_data.find_one({"_id": int(user_id)})
            if user:
                return user.get("ban_status", {}).get("is_banned", False)
            return False
        except Exception as e:
            logging.error(f"ᴇʀʀᴏʀ ᴄʜᴇᴄᴋɪɴɢ ʙᴀɴ ꜰᴏʀ {user_id}: {e}")
            return False

    # ══════════════════════════════════════════════════════
    #  MAPPED CHANNELS
    # ══════════════════════════════════════════════════════

    async def set_mapped_channel(self, anime_name: str, channel_id: int):
        if self.mapped_channels is not None:
            await self.mapped_channels.update_one(
                {"_id": channel_id},
                {"$addToSet": {"anime_names": anime_name.lower()}},
                upsert=True
            )

    async def remove_mapped_channel(self, channel_id: int):
        if self.mapped_channels is not None:
            await self.mapped_channels.delete_one({"_id": channel_id})

    async def get_mapped_channel(self, title: str):
        if self.mapped_channels is None:
            return None
        cursor = self.mapped_channels.find({})
        channels = await cursor.to_list(None)
        title_lower = title.lower()

        for doc in channels:
            for mapped_name in doc.get("anime_names", []):
                # Ensure a more accurate match by comparing standard length
                if mapped_name == title_lower or (len(mapped_name) > 3 and mapped_name in title_lower):
                    return doc["_id"]
        return None

    async def get_all_mappings(self):
        if self.mapped_channels is None:
            return []
        cursor = self.mapped_channels.find({})
        return await cursor.to_list(length=1000)

    # ══════════════════════════════════════════════════════
    #  USER SETTINGS  (generic key-value per user)
    # ══════════════════════════════════════════════════════

    async def get_user_setting(self, user_id: int, key: str, default=None):
        if self.settings is None:
            return default
        user = await self.settings.find_one({"_id": user_id})
        if user and key in user:
            return user[key]
        return default

    async def set_user_setting(self, user_id: int, key: str, value):
        if self.settings is not None:
            await self.settings.update_one(
                {"_id": user_id},
                {"$set": {key: value}},
                upsert=True
            )

    async def get_processed_count(self) -> int:
        if self.processed is None:
            return 0
        return await self.processed.count_documents({})

    # ══════════════════════════════════════════════════════
    #  PROCESSED EPISODES
    # ══════════════════════════════════════════════════════

    async def is_processed(self, ep_identifier: str) -> bool:
        if self.processed is None:
            return False
        return await self.processed.find_one({"_id": ep_identifier}) is not None

    async def mark_processed(self, ep_identifier: str):
        if self.processed is not None:
            await self.processed.update_one(
                {"_id": ep_identifier},
                {"$set": {"processed": True}},
                upsert=True
            )

    # ══════════════════════════════════════════════════════
    #  ADMIN MANAGEMENT
    # ══════════════════════════════════════════════════════

    async def is_admin(self, user_id: int) -> bool:
        if self.admins_data is None:
            return False
        return bool(await self.admins_data.find_one({"_id": int(user_id)}))

    async def add_admin(self, user_id: int, name: str = None) -> bool:
        if self.admins_data is None:
            return False
        try:
            await self.admins_data.update_one(
                {"_id": int(user_id)},
                {"$set": {"_id": int(user_id), "name": name, "added_at": datetime.utcnow()}},
                upsert=True
            )
            return True
        except Exception as e:
            logging.error(f"ᴇʀʀᴏʀ ᴀᴅᴅɪɴɢ ᴀᴅᴍɪɴ {user_id}: {e}")
            return False

    async def remove_admin(self, user_id: int) -> bool:
        if self.admins_data is None:
            return False
        result = await self.admins_data.delete_one({"_id": int(user_id)})
        return result.deleted_count > 0

    async def list_admins(self) -> list:
        if self.admins_data is None:
            return []
        admins = await self.admins_data.find({}).to_list(None)
        return [a["_id"] for a in admins]

    # Alias used by old code
    async def get_all_admins(self) -> list:
        if self.admins_data is None:
            return []
        cursor = self.admins_data.find({})
        return await cursor.to_list(length=100)

    # ══════════════════════════════════════════════════════
    #  FORCE-SUB CHANNEL MANAGEMENT
    # ══════════════════════════════════════════════════════

    async def add_fsub_channel(self, channel_id: int) -> bool:
        if self.fsub_data is None:
            return False
        try:
            await self.fsub_data.update_one(
                {"channel_id": channel_id},
                {"$set": {
                    "channel_id": channel_id,
                    "created_at": datetime.utcnow(),
                    "status": "active",
                    "mode": "off"
                }},
                upsert=True
            )
            return True
        except Exception as e:
            logging.error(f"ᴇʀʀᴏʀ ᴀᴅᴅɪɴɢ ꜰꜱᴜʙ ᴄʜᴀɴɴᴇʟ {channel_id}: {e}")
            return False

    async def remove_fsub_channel(self, channel_id: int) -> bool:
        if self.fsub_data is None:
            return False
        result = await self.fsub_data.delete_one({"channel_id": channel_id})
        return result.deleted_count > 0

    async def get_fsub_channels(self) -> List[int]:
        if self.fsub_data is None:
            return []
        cursor   = self.fsub_data.find({"status": "active"})
        channels = await cursor.to_list(None)
        return [ch["channel_id"] for ch in channels if "channel_id" in ch]

    # Alias for backward compatibility
    async def show_channels(self) -> List[int]:
        return await self.get_fsub_channels()

    async def get_channel_mode(self, channel_id: int) -> str:
        if self.fsub_data is None:
            return "off"
        data = await self.fsub_data.find_one({"channel_id": channel_id})
        return data.get("mode", "off") if data else "off"

    # Alias for backward compatibility
    async def get_channel_mode_all(self, channel_id: int) -> str:
        return await self.get_channel_mode(channel_id)

    async def set_channel_mode(self, channel_id: int, mode: str):
        if self.fsub_data is not None:
            await self.fsub_data.update_one(
                {"channel_id": channel_id},
                {"$set": {"mode": mode}},
                upsert=True
            )

    # ══════════════════════════════════════════════════════
    #  REQUEST FORCE-SUB HELPERS
    # ══════════════════════════════════════════════════════

    async def req_user(self, channel_id: int, user_id: int):
        if self.rqst_fsub_Channel_data is not None:
            await self.rqst_fsub_Channel_data.update_one(
                {"channel_id": int(channel_id)},
                {"$addToSet": {"user_ids": int(user_id)}},
                upsert=True
            )

    async def del_req_user(self, channel_id: int, user_id: int):
        if self.rqst_fsub_Channel_data is not None:
            await self.rqst_fsub_Channel_data.update_one(
                {"channel_id": channel_id},
                {"$pull": {"user_ids": user_id}}
            )

    async def req_user_exist(self, channel_id: int, user_id: int) -> bool:
        if self.rqst_fsub_Channel_data is None:
            return False
        found = await self.rqst_fsub_Channel_data.find_one({
            "channel_id": int(channel_id),
            "user_ids":   int(user_id)
        })
        return bool(found)

    # ══════════════════════════════════════════════════════
    #  FAVORITES
    # ══════════════════════════════════════════════════════

    async def add_favorite(self, user_id: int, anime_id: str, title: str):
        if self.favorites is not None:
            await self.favorites.update_one(
                {"user_id": user_id},
                {"$addToSet": {"items": {"id": anime_id, "title": title}}},
                upsert=True
            )

    async def remove_favorite(self, user_id: int, anime_id: str):
        if self.favorites is not None:
            await self.favorites.update_one(
                {"user_id": user_id},
                {"$pull": {"items": {"id": anime_id}}}
            )

    async def get_favorites(self, user_id: int):
        if self.favorites is None:
            return []
        data = await self.favorites.find_one({"user_id": user_id})
        return data.get("items", []) if data else []

    async def get_db_stats(self):
        """Fetch database storage statistics."""
        if self.db is None:
            return None
        try:
            stats = await self.db.command("dbStats")
            return {
                "data_size": stats.get("dataSize", 0),
                "storage_size": stats.get("storageSize", 0),
                "index_size": stats.get("indexSize", 0),
                "total_size": stats.get("storageSize", 0) + stats.get("indexSize", 0)
            }
        except Exception as e:
            logging.error(f"ᴇʀʀᴏʀ ꜰᴇᴛᴄʜɪɴɢ ᴅʙ ꜱᴛᴀᴛꜱ: {e}")
            return None


# ── Singleton instances ──────────────────────────────────────────────────────
db = Database(MONGO_URL)

# Backward-compat alias so any existing code using `Seishiro.x` keeps working
Seishiro = db
