"""
Database persistence and SQLite management for ConsultBae Unified Database.
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from .models import UnifiedCandidate, SourceRecord, AudioSubmission

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "consultbae.db"


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Returns a SQLite connection with row factory enabled."""
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Creates database schema and indexes if they do not exist."""
    conn = get_db_connection(db_path)
    with conn:
        # 1. Unified candidates table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS unified_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE,
                phone TEXT UNIQUE,
                city TEXT,
                skills TEXT, -- JSON array of strings
                experience_years REAL,
                current_ctc_lpa REAL,
                current_ctc_raw_inr INTEGER,
                hourly_rate_inr REAL,
                monthly_rate_inr REAL,
                status TEXT DEFAULT 'Active',
                verified INTEGER, -- 1=True, 0=False, NULL=Unknown
                projects_completed INTEGER DEFAULT 0,
                applied_date TEXT,
                source_count INTEGER DEFAULT 1,
                sources_merged TEXT, -- JSON array of source names
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 2. Source records table (provenance / audit trail)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER,
                source_name TEXT NOT NULL,
                original_row_idx INTEGER,
                raw_data TEXT NOT NULL, -- JSON string
                normalized_name TEXT,
                normalized_email TEXT,
                normalized_phone TEXT,
                normalized_city TEXT,
                issues_found TEXT, -- JSON array of string descriptions
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (candidate_id) REFERENCES unified_candidates(id) ON DELETE SET NULL
            )
        """)

        # 3. Audio submissions table (for Task 3)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audio_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER,
                worker_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                audio_filename TEXT NOT NULL,
                audio_filepath TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                duration_seconds REAL NOT NULL,
                sample_rate_khz REAL NOT NULL,
                bitrate_kbps REAL NOT NULL,
                loudness_dbfs REAL NOT NULL,
                snr_db REAL,
                noise_floor_dbfs REAL,
                clipping_ratio REAL DEFAULT 0.0,
                quality_verdict TEXT NOT NULL,
                quality_notes TEXT,
                submitted_at TEXT NOT NULL,
                FOREIGN KEY (candidate_id) REFERENCES unified_candidates(id) ON DELETE SET NULL
            )
        """)

        # Indexes for fast querying & deduplication
        conn.execute("CREATE INDEX IF NOT EXISTS idx_candidates_email ON unified_candidates(email)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_candidates_phone ON unified_candidates(phone)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_candidates_name ON unified_candidates(full_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audio_phone ON audio_submissions(phone)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_source_candidate ON source_records(candidate_id)")

    conn.close()


def save_unified_candidate(candidate: UnifiedCandidate, db_path: Optional[Path] = None) -> int:
    """Inserts a new unified candidate into SQLite and returns the inserted ID."""
    conn = get_db_connection(db_path)
    with conn:
        cursor = conn.execute("""
            INSERT INTO unified_candidates (
                full_name, email, phone, city, skills, experience_years,
                current_ctc_lpa, current_ctc_raw_inr, hourly_rate_inr, monthly_rate_inr,
                status, verified, projects_completed, applied_date, source_count,
                sources_merged, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            candidate.full_name,
            candidate.email,
            candidate.phone,
            candidate.city,
            json.dumps(candidate.skills),
            candidate.experience_years,
            candidate.current_ctc_lpa,
            candidate.current_ctc_raw_inr,
            candidate.hourly_rate_inr,
            candidate.monthly_rate_inr,
            candidate.status,
            1 if candidate.verified is True else (0 if candidate.verified is False else None),
            candidate.projects_completed,
            candidate.applied_date,
            candidate.source_count,
            json.dumps(candidate.sources_merged),
            candidate.created_at,
            candidate.updated_at
        ))
        cand_id = cursor.lastrowid
    conn.close()
    return cand_id


def update_unified_candidate(candidate: UnifiedCandidate, db_path: Optional[Path] = None) -> None:
    """Updates an existing unified candidate in SQLite."""
    conn = get_db_connection(db_path)
    with conn:
        conn.execute("""
            UPDATE unified_candidates SET
                full_name = ?,
                email = ?,
                phone = ?,
                city = ?,
                skills = ?,
                experience_years = ?,
                current_ctc_lpa = ?,
                current_ctc_raw_inr = ?,
                hourly_rate_inr = ?,
                monthly_rate_inr = ?,
                status = ?,
                verified = ?,
                projects_completed = ?,
                applied_date = ?,
                source_count = ?,
                sources_merged = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            candidate.full_name,
            candidate.email,
            candidate.phone,
            candidate.city,
            json.dumps(candidate.skills),
            candidate.experience_years,
            candidate.current_ctc_lpa,
            candidate.current_ctc_raw_inr,
            candidate.hourly_rate_inr,
            candidate.monthly_rate_inr,
            candidate.status,
            1 if candidate.verified is True else (0 if candidate.verified is False else None),
            candidate.projects_completed,
            candidate.applied_date,
            candidate.source_count,
            json.dumps(candidate.sources_merged),
            candidate.updated_at,
            candidate.id
        ))
    conn.close()


def save_source_record(candidate_id: int, rec: SourceRecord, db_path: Optional[Path] = None) -> int:
    """Saves a source record provenance link into SQLite."""
    conn = get_db_connection(db_path)
    with conn:
        cursor = conn.execute("""
            INSERT INTO source_records (
                candidate_id, source_name, original_row_idx, raw_data,
                normalized_name, normalized_email, normalized_phone, normalized_city,
                issues_found
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            candidate_id,
            rec.source_name,
            rec.original_row_idx,
            json.dumps(rec.raw_data),
            rec.normalized_name,
            rec.normalized_email,
            rec.normalized_phone,
            rec.normalized_city,
            json.dumps(rec.issues_found)
        ))
        record_id = cursor.lastrowid
    conn.close()
    return record_id


def save_audio_submission(sub: AudioSubmission, db_path: Optional[Path] = None) -> int:
    """Inserts a new audio submission record and returns the inserted ID."""
    conn = get_db_connection(db_path)
    with conn:
        cursor = conn.execute("""
            INSERT INTO audio_submissions (
                candidate_id, worker_name, phone, audio_filename, audio_filepath,
                file_size_bytes, duration_seconds, sample_rate_khz, bitrate_kbps,
                loudness_dbfs, snr_db, noise_floor_dbfs, clipping_ratio,
                quality_verdict, quality_notes, submitted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sub.candidate_id,
            sub.worker_name,
            sub.phone,
            sub.audio_filename,
            sub.audio_filepath,
            sub.file_size_bytes,
            sub.duration_seconds,
            sub.sample_rate_khz,
            sub.bitrate_kbps,
            sub.loudness_dbfs,
            sub.snr_db,
            sub.noise_floor_dbfs,
            sub.clipping_ratio,
            sub.quality_verdict,
            sub.quality_notes,
            sub.submitted_at
        ))
        sub_id = cursor.lastrowid
    conn.close()
    return sub_id


def get_all_unified_candidates(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Fetches all unified candidate records as dictionaries."""
    conn = get_db_connection(db_path)
    rows = conn.execute("SELECT * FROM unified_candidates ORDER BY id ASC").fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["skills"] = json.loads(d["skills"]) if d["skills"] else []
        d["sources_merged"] = json.loads(d["sources_merged"]) if d["sources_merged"] else []
        d["verified"] = bool(d["verified"]) if d["verified"] is not None else None
        results.append(d)
    conn.close()
    return results


def get_all_audio_submissions(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Fetches all audio submissions sorted by newest first."""
    conn = get_db_connection(db_path)
    rows = conn.execute("SELECT * FROM audio_submissions ORDER BY id DESC").fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


def find_candidate_by_phone_or_email(
    phone: Optional[str] = None,
    email: Optional[str] = None,
    name: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Searches for an existing candidate matching normalized phone, email, or name."""
    conn = get_db_connection(db_path)
    row = None
    if phone:
        row = conn.execute("SELECT * FROM unified_candidates WHERE phone = ?", (phone,)).fetchone()
    if not row and email:
        row = conn.execute("SELECT * FROM unified_candidates WHERE email = ?", (email,)).fetchone()
    if not row and name:
        row = conn.execute("SELECT * FROM unified_candidates WHERE LOWER(full_name) = LOWER(?)", (name,)).fetchone()

    if row:
        d = dict(row)
        d["skills"] = json.loads(d["skills"]) if d["skills"] else []
        d["sources_merged"] = json.loads(d["sources_merged"]) if d["sources_merged"] else []
        conn.close()
        return d

    conn.close()
    return None
