from __future__ import annotations

import sqlite3
from typing import Any

from backend.config import DATABASE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    artist      TEXT    DEFAULT 'Unknown',
    album       TEXT    DEFAULT '',
    duration    REAL    DEFAULT 0,
    file_hash   TEXT    UNIQUE,
    artwork_url TEXT    DEFAULT '',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fingerprints (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id     INTEGER NOT NULL,
    hash        TEXT    NOT NULL,
    time_offset INTEGER NOT NULL,
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fp_hash ON fingerprints(hash);
"""


class Database:
    """Thin wrapper around a single SQLite connection."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or DATABASE_PATH
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ── Songs ────────────────────────────────────────────────────────────

    def add_song(
        self,
        title: str,
        artist: str = "Unknown",
        album: str = "",
        duration: float = 0.0,
        file_hash: str = "",
        artwork_url: str = "",
    ) -> int | None:
        cursor = self.conn.execute(
            "INSERT OR IGNORE INTO songs "
            "(title, artist, album, duration, file_hash, artwork_url) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (title, artist, album, duration, file_hash, artwork_url),
        )
        self.conn.commit()
        if cursor.lastrowid:
            return cursor.lastrowid
        row = self.conn.execute(
            "SELECT id FROM songs WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        return row[0] if row else None

    def get_song(self, song_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT id, title, artist, album, duration, file_hash, artwork_url, created_at "
            "FROM songs WHERE id = ?",
            (song_id,),
        ).fetchone()
        if row:
            return dict(
                id=row[0],
                title=row[1],
                artist=row[2],
                album=row[3],
                duration=row[4],
                file_hash=row[5],
                artwork_url=row[6],
                created_at=str(row[7]),
            )
        return None

    def get_all_songs(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id, title, artist, album, duration, artwork_url "
            "FROM songs ORDER BY created_at DESC"
        ).fetchall()
        return [
            dict(id=r[0], title=r[1], artist=r[2], album=r[3], duration=r[4], artwork_url=r[5])
            for r in rows
        ]

    def song_exists(self, file_hash: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM songs WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        return row is not None

    def delete_song(self, song_id: int) -> None:
        self.conn.execute("DELETE FROM fingerprints WHERE song_id = ?", (song_id,))
        self.conn.execute("DELETE FROM songs WHERE id = ?", (song_id,))
        self.conn.commit()

    # ── Fingerprints ─────────────────────────────────────────────────────

    def add_fingerprints(self, song_id: int, fingerprints: list[tuple[str, int]]) -> None:
        """Store a batch of (hash, time_offset) fingerprints for a song."""
        self.conn.executemany(
            "INSERT INTO fingerprints (song_id, hash, time_offset) VALUES (?, ?, ?)",
            [(song_id, h, o) for h, o in fingerprints],
        )
        self.conn.commit()

    def get_matches(self, hash_values: list[str]) -> list[tuple[str, int, int]]:
        """Look up hashes. Returns [(hash, song_id, time_offset), ...]."""
        if not hash_values:
            return []
        placeholders = ",".join(["?"] * len(hash_values))
        return self.conn.execute(
            f"SELECT hash, song_id, time_offset FROM fingerprints "
            f"WHERE hash IN ({placeholders})",
            hash_values,
        ).fetchall()

    # ── Stats ────────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, int]:
        songs = self.conn.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
        fps = self.conn.execute("SELECT COUNT(*) FROM fingerprints").fetchone()[0]
        return {"songs": songs, "fingerprints": fps}

    def close(self) -> None:
        self.conn.close()
