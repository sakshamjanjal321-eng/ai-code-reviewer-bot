import os
import json
import sqlite3
import logging
from typing import List

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_FILE = os.path.join(BASE_DIR, "reviews_history.json")

class HistoryStore:
    def __init__(self):
        self.db_path = os.getenv("SQLITE_DB_PATH")
        self._init_db()

    def _init_db(self):
        if not self.db_path:
            logger.info("SQLITE_DB_PATH not configured. History store using fallback reviews_history.json file.")
            return
        try:
            # Resolve db path relative to project folder if it's not absolute
            if not os.path.isabs(self.db_path):
                self.db_path = os.path.join(BASE_DIR, self.db_path)
            
            # Ensure folder exists
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS review_history (
                    id TEXT PRIMARY KEY,
                    repo TEXT,
                    pr_number INTEGER,
                    type TEXT,
                    summary TEXT,
                    comment_count INTEGER,
                    errors INTEGER,
                    warnings INTEGER,
                    infos INTEGER,
                    timestamp TEXT,
                    status TEXT
                )
            """)
            conn.commit()
            conn.close()
            logger.info(f"SQLite history datastore successfully initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite database at {self.db_path}: {e}. Falling back to JSON file.")
            self.db_path = None

    def load_history(self) -> List[dict]:
        if self.db_path:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM review_history ORDER BY timestamp DESC LIMIT 50")
                rows = cursor.fetchall()
                history = [dict(row) for row in rows]
                conn.close()
                return history
            except Exception as e:
                logger.error(f"Failed to load history from SQLite: {e}. Falling back to JSON load.")
        
        # Fallback load
        if not os.path.exists(JSON_FILE):
            return []
        try:
            with open(JSON_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load history from JSON file: {e}")
            return []

    def save_history(self, entry: dict):
        if self.db_path:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO review_history 
                    (id, repo, pr_number, type, summary, comment_count, errors, warnings, infos, timestamp, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.get("id"),
                    entry.get("repo"),
                    entry.get("pr_number"),
                    entry.get("type"),
                    entry.get("summary"),
                    entry.get("comment_count", 0),
                    entry.get("errors", 0),
                    entry.get("warnings", 0),
                    entry.get("infos", 0),
                    entry.get("timestamp"),
                    entry.get("status")
                ))
                conn.commit()
                conn.close()
                logger.info(f"Successfully saved review history entry in SQLite db: {entry.get('id')}")
                return
            except Exception as e:
                logger.error(f"Failed to save history to SQLite: {e}. Falling back to JSON save.")
        
        # Fallback save
        try:
            # To preserve fallback consistency, load existing records from JSON first
            history_json = []
            if os.path.exists(JSON_FILE):
                try:
                    with open(JSON_FILE, "r") as f:
                        history_json = json.load(f)
                except Exception:
                    pass
            history_json.insert(0, entry)
            history_json = history_json[:50]
            with open(JSON_FILE, "w") as f:
                json.dump(history_json, f, indent=2)
            logger.info(f"Successfully saved review history entry in JSON: {entry.get('id')}")
        except Exception as e:
            logger.error(f"Failed to save history to JSON file: {e}")

# Global instance
history_store = HistoryStore()
