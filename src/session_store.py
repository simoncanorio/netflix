"""
Almacenamiento Persistente de Sesiones de Usuario en SQLite (WAL Mode).
Permite que el aprendizaje del usuario (géneros, países, grafo de actores 1-hop/2-hop,
Mi Lista y estadísticas del Contextual Bandit UCB1) sobreviva a reinicios del servidor.
"""

import json
import sqlite3
import threading
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR


DEFAULT_PROFILE_TEMPLATE = {
    "genres": {},
    "countries": {},
    "actors": {},
    "suggested_actors": {},
    "bandit_arms": {
        "actor_focus": {"pulls": 1, "rewards": 1.0},
        "genre_focus": {"pulls": 1, "rewards": 1.0},
        "global_hit": {"pulls": 1, "rewards": 1.0}
    },
    "active_bandit_arm": "global_hit",
    "interacted_tconsts": [],
    "liked_tconsts": [],
    "disliked_tconsts": [],
    "continue_watching": [],
    "my_list": [],
    "signal_score": 0.0,
    "interaction_count": 0,
    "recent_actions": []
}


class SessionStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or (DATA_DIR / "user_sessions.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: dict[str, dict] = {}
        self._init_db()

    def _init_db(self):
        with self._lock:
            con = sqlite3.connect(str(self.db_path))
            try:
                con.execute("PRAGMA journal_mode=WAL;")
                con.execute("""
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        session_id TEXT PRIMARY KEY,
                        profile_json TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                con.commit()
            finally:
                con.close()

    def get_or_create(self, session_id: str) -> dict:
        if session_id in self._cache:
            return self._cache[session_id]

        with self._lock:
            con = sqlite3.connect(str(self.db_path))
            try:
                row = con.execute(
                    "SELECT profile_json FROM user_profiles WHERE session_id = ?",
                    (session_id,)
                ).fetchone()
                if row:
                    profile = json.loads(row[0])
                else:
                    profile = json.loads(json.dumps(DEFAULT_PROFILE_TEMPLATE))
                    con.execute(
                        "INSERT INTO user_profiles (session_id, profile_json) VALUES (?, ?)",
                        (session_id, json.dumps(profile, ensure_ascii=False))
                    )
                    con.commit()
            finally:
                con.close()

        # Asegurar todas las claves de versiones nuevas
        for k, default_val in DEFAULT_PROFILE_TEMPLATE.items():
            if k not in profile:
                profile[k] = json.loads(json.dumps(default_val))

        self._cache[session_id] = profile
        return profile

    def save(self, session_id: str, profile: dict):
        self._cache[session_id] = profile
        payload = json.dumps(profile, ensure_ascii=False)
        with self._lock:
            con = sqlite3.connect(str(self.db_path))
            try:
                con.execute("""
                    INSERT INTO user_profiles (session_id, profile_json, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(session_id) DO UPDATE SET
                        profile_json = excluded.profile_json,
                        updated_at = CURRENT_TIMESTAMP;
                """, (session_id, payload))
                con.commit()
            finally:
                con.close()

    def reset(self, session_id: str) -> dict:
        """Reinicia una sesión a su estado virgen (0.0 pts) y la persiste en SQLite."""
        fresh = json.loads(json.dumps(DEFAULT_PROFILE_TEMPLATE))
        self.save(session_id, fresh)
        return fresh
