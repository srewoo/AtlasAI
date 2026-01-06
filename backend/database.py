"""
SQLite Database Module - Local file-based storage
Replaces MongoDB for simpler local development
"""

import aiosqlite
import json
import os
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Database file path
DB_PATH = Path(__file__).parent / "atlas_ai.db"


class Database:
    """Async SQLite database wrapper with MongoDB-like interface"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self._connection = None

    async def connect(self):
        """Initialize database connection and create tables"""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._create_tables()
        logger.info(f"Connected to SQLite database: {self.db_path}")

    async def close(self):
        """Close database connection"""
        if self._connection:
            await self._connection.close()
            logger.info("Database connection closed")

    async def _create_tables(self):
        """Create necessary tables if they don't exist"""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS user_settings (
                id TEXT PRIMARY KEY,
                user_id TEXT UNIQUE NOT NULL,
                settings TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_message TEXT NOT NULL,
                bot_response TEXT NOT NULL,
                sources TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id);
            CREATE INDEX IF NOT EXISTS idx_chat_timestamp ON chat_history(timestamp);
            CREATE INDEX IF NOT EXISTS idx_settings_user ON user_settings(user_id);
        """)
        await self._connection.commit()

    # User Settings Methods
    async def get_user_settings(self, user_id: str) -> Optional[Dict]:
        """Get settings for a user"""
        async with self._connection.execute(
            "SELECT * FROM user_settings WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "settings": json.loads(row["settings"]),
                    "timestamp": row["timestamp"]
                }
            return None

    async def save_user_settings(self, user_id: str, settings: Dict, doc_id: str = None) -> bool:
        """Save or update user settings"""
        try:
            existing = await self.get_user_settings(user_id)
            timestamp = datetime.now(timezone.utc).isoformat()

            if existing:
                await self._connection.execute(
                    "UPDATE user_settings SET settings = ?, timestamp = ? WHERE user_id = ?",
                    (json.dumps(settings), timestamp, user_id)
                )
            else:
                doc_id = doc_id or f"settings_{user_id}"
                await self._connection.execute(
                    "INSERT INTO user_settings (id, user_id, settings, timestamp) VALUES (?, ?, ?, ?)",
                    (doc_id, user_id, json.dumps(settings), timestamp)
                )

            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False

    # Chat History Methods
    async def add_chat_message(self, session_id: str, user_message: str,
                                bot_response: str, sources: List[str], doc_id: str = None) -> bool:
        """Add a chat message to history"""
        try:
            doc_id = doc_id or f"chat_{datetime.now().timestamp()}"
            timestamp = datetime.now(timezone.utc).isoformat()

            await self._connection.execute(
                """INSERT INTO chat_history
                   (id, session_id, user_message, bot_response, sources, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (doc_id, session_id, user_message, bot_response, json.dumps(sources), timestamp)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding chat message: {e}")
            return False

    async def get_chat_history(self, session_id: str, limit: int = 100) -> List[Dict]:
        """Get chat history for a session"""
        async with self._connection.execute(
            """SELECT * FROM chat_history
               WHERE session_id = ?
               ORDER BY timestamp ASC
               LIMIT ?""",
            (session_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "user_message": row["user_message"],
                    "bot_response": row["bot_response"],
                    "sources": json.loads(row["sources"]),
                    "timestamp": row["timestamp"]
                }
                for row in rows
            ]

    async def get_recent_chat_history(self, session_id: str, limit: int = 5) -> List[Dict]:
        """Get most recent chat messages for context"""
        async with self._connection.execute(
            """SELECT * FROM chat_history
               WHERE session_id = ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (session_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            # Reverse to get chronological order
            result = [
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "user_message": row["user_message"],
                    "bot_response": row["bot_response"],
                    "sources": json.loads(row["sources"]),
                    "timestamp": row["timestamp"]
                }
                for row in rows
            ]
            result.reverse()
            return result

    async def clear_chat_history(self, session_id: str) -> int:
        """Clear chat history for a session"""
        try:
            cursor = await self._connection.execute(
                "DELETE FROM chat_history WHERE session_id = ?",
                (session_id,)
            )
            await self._connection.commit()
            return cursor.rowcount
        except Exception as e:
            logger.error(f"Error clearing chat history: {e}")
            return 0


# Global database instance
db = Database()


async def init_database():
    """Initialize the database connection"""
    await db.connect()


async def close_database():
    """Close the database connection"""
    await db.close()
