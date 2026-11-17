"""SQLite persistence for voice profiles and generation history."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from utils.helpers import utc_now_iso


class DuplicateProfileError(ValueError):
    pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS voice_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    reference_audio_path TEXT NOT NULL DEFAULT '',
    original_audio_path TEXT NOT NULL DEFAULT '',
    duration_sec REAL,
    consent_confirmed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS generated_audio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER REFERENCES voice_profiles(id) ON DELETE SET NULL,
    profile_name TEXT NOT NULL DEFAULT '',
    input_text TEXT NOT NULL,
    language TEXT NOT NULL,
    output_audio_path TEXT NOT NULL,
    model_name TEXT NOT NULL,
    duration_sec REAL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_generated_created ON generated_audio(created_at DESC);
"""

_PROFILE_FIELDS = {"profile_name", "reference_audio_path", "original_audio_path", "duration_sec"}


class Database:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        # One short-lived connection per operation: safe with Streamlit's threads.
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:  # commit / rollback
                yield conn
        finally:
            conn.close()

    # ----------------------------------------------------------------- profiles
    def add_profile(self, profile_name: str, consent_confirmed: bool, duration_sec: float | None = None) -> int:
        now = utc_now_iso()
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO voice_profiles (profile_name, duration_sec, consent_confirmed, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (profile_name, duration_sec, int(consent_confirmed), now, now),
                )
                return int(cur.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise DuplicateProfileError(f"A profile named '{profile_name}' already exists.") from exc

    def update_profile(self, profile_id: int, **fields: Any) -> None:
        unknown = set(fields) - _PROFILE_FIELDS
        if unknown:
            raise ValueError(f"Cannot update fields: {sorted(unknown)}")
        if not fields:
            return
        assignments = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [utc_now_iso(), profile_id]
        try:
            with self._connect() as conn:
                conn.execute(f"UPDATE voice_profiles SET {assignments}, updated_at = ? WHERE id = ?", values)
        except sqlite3.IntegrityError as exc:
            raise DuplicateProfileError("Another profile already uses that name.") from exc

    def get_profile(self, profile_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM voice_profiles WHERE id = ?", (profile_id,)).fetchone()
        return dict(row) if row else None

    def list_profiles(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM voice_profiles ORDER BY created_at DESC, id DESC").fetchall()
        return [dict(r) for r in rows]

    def delete_profile(self, profile_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM voice_profiles WHERE id = ?", (profile_id,))
            return cur.rowcount > 0

    def count_profiles(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM voice_profiles").fetchone()[0])

    # -------------------------------------------------------------- generations
    def add_generation(
        self,
        *,
        profile_id: int | None,
        profile_name: str,
        input_text: str,
        language: str,
        output_audio_path: str,
        model_name: str,
        duration_sec: float | None,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO generated_audio (profile_id, profile_name, input_text, language, output_audio_path, "
                "model_name, duration_sec, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (profile_id, profile_name, input_text, language, output_audio_path, model_name, duration_sec, utc_now_iso()),
            )
            return int(cur.lastrowid)

    def get_generation(self, generation_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM generated_audio WHERE id = ?", (generation_id,)).fetchone()
        return dict(row) if row else None

    def list_generations(
        self,
        limit: int = 50,
        offset: int = 0,
        profile_id: int | None = None,
        language: str | None = None,
    ) -> list[dict]:
        clauses, params = [], []
        if profile_id is not None:
            clauses.append("profile_id = ?")
            params.append(profile_id)
        if language:
            clauses.append("language = ?")
            params.append(language)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM generated_audio {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    def generations_for_profile(self, profile_id: int) -> list[dict]:
        return self.list_generations(limit=100000, profile_id=profile_id)

    def delete_generation(self, generation_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM generated_audio WHERE id = ?", (generation_id,))
            return cur.rowcount > 0

    def count_generations(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM generated_audio").fetchone()[0])
