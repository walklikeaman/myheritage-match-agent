"""
SQLite database for tracking processed matches and flagged items.
Provides resume capability — on restart, already-processed match IDs are skipped.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger
from config import DB_FILE


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # safer for long-running writes
    return conn


def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS processed_matches (
                id TEXT PRIMARY KEY,
                match_type TEXT NOT NULL,       -- 'smart' or 'record'
                person_id TEXT,
                person_name TEXT,
                confidence INTEGER,
                decision TEXT NOT NULL,         -- 'accepted', 'rejected', 'skipped', 'flagged', 'error'
                data_saved TEXT,                -- JSON: list of fields actually saved to tree
                processed_at TEXT NOT NULL,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS flagged_matches (
                id TEXT PRIMARY KEY,
                reason TEXT NOT NULL,           -- 'name_mismatch', 'date_conflict', 'relationship_restructure'
                match_data TEXT NOT NULL,       -- full JSON for manual review
                flagged_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS run_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                match_type TEXT,                -- 'smart', 'record', or 'both'
                total_seen INTEGER DEFAULT 0,
                total_accepted INTEGER DEFAULT 0,
                total_skipped INTEGER DEFAULT 0,
                total_flagged INTEGER DEFAULT 0,
                total_errors INTEGER DEFAULT 0,
                dry_run INTEGER DEFAULT 0
            );
        """)
    logger.info(f"Database initialized at {DB_FILE}")


def is_processed(match_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM processed_matches WHERE id = ?", (match_id,)
        ).fetchone()
        return row is not None


def record_match(
    match_id: str,
    match_type: str,
    decision: str,
    person_id: Optional[str] = None,
    person_name: Optional[str] = None,
    confidence: Optional[int] = None,
    data_saved: Optional[list] = None,
    notes: Optional[str] = None,
):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO processed_matches
                (id, match_type, person_id, person_name, confidence, decision, data_saved, processed_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                match_type,
                person_id,
                person_name,
                confidence,
                decision,
                json.dumps(data_saved) if data_saved else None,
                datetime.utcnow().isoformat(),
                notes,
            ),
        )


def flag_match(match_id: str, reason: str, match_data: dict):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO flagged_matches (id, reason, match_data, flagged_at)
            VALUES (?, ?, ?, ?)
            """,
            (match_id, reason, json.dumps(match_data), datetime.utcnow().isoformat()),
        )


def start_run(match_type: str, dry_run: bool) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO run_log (started_at, match_type, dry_run) VALUES (?, ?, ?)",
            (datetime.utcnow().isoformat(), match_type, int(dry_run)),
        )
        return cursor.lastrowid


def finish_run(run_id: int, stats: dict):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE run_log SET
                finished_at = ?,
                total_seen = ?,
                total_accepted = ?,
                total_skipped = ?,
                total_flagged = ?,
                total_errors = ?
            WHERE id = ?
            """,
            (
                datetime.utcnow().isoformat(),
                stats.get("seen", 0),
                stats.get("accepted", 0),
                stats.get("skipped", 0),
                stats.get("flagged", 0),
                stats.get("errors", 0),
                run_id,
            ),
        )


def get_stats() -> dict:
    with get_connection() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN decision = 'accepted' THEN 1 ELSE 0 END) AS accepted,
                SUM(CASE WHEN decision = 'skipped' THEN 1 ELSE 0 END) AS skipped,
                SUM(CASE WHEN decision = 'flagged' THEN 1 ELSE 0 END) AS flagged,
                SUM(CASE WHEN decision = 'error' THEN 1 ELSE 0 END) AS errors
            FROM processed_matches
        """).fetchone()
        flagged = conn.execute("SELECT COUNT(*) AS n FROM flagged_matches").fetchone()
        return {
            "total_processed": row["total"],
            "accepted": row["accepted"] or 0,
            "skipped": row["skipped"] or 0,
            "flagged_decisions": row["flagged"] or 0,
            "errors": row["errors"] or 0,
            "pending_manual_review": flagged["n"],
        }
