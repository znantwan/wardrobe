import re
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional


def _normalize(name: str) -> str:
    """Lowercase, strip punctuation/spaces — used for deduplication keys."""
    return re.sub(r"[^a-z0-9]", "", name.lower().strip())


SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    normalized_name     TEXT UNIQUE NOT NULL,
    description         TEXT,
    funding_amount      TEXT,
    funding_round       TEXT,
    funding_date        TEXT,
    website             TEXT,
    linkedin_url        TEXT,
    crunchbase_url      TEXT,
    source              TEXT,
    source_url          TEXT,
    alumni_searched_at  TIMESTAMP,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contacts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id       INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name             TEXT NOT NULL,
    normalized_name  TEXT NOT NULL,
    title            TEXT,
    email            TEXT,
    linkedin_url     TEXT,
    school           TEXT DEFAULT 'Stanford GSB',
    graduation_year  INTEGER,
    source           TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, normalized_name)
);

CREATE TABLE IF NOT EXISTS search_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    query         TEXT,
    source        TEXT,
    ran_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    result_count  INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_companies_norm  ON companies (normalized_name);
CREATE INDEX IF NOT EXISTS idx_contacts_co     ON contacts  (company_id);
CREATE INDEX IF NOT EXISTS idx_contacts_norm   ON contacts  (normalized_name);
"""


class Database:
    def __init__(self, db_path: str = "recruiting.db"):
        self.db_path = db_path

    # ── Internal ──────────────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def initialize(self):
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    def reset(self):
        with self._conn() as conn:
            conn.executescript(
                "DROP TABLE IF EXISTS search_log;"
                "DROP TABLE IF EXISTS contacts;"
                "DROP TABLE IF EXISTS companies;"
            )
        self.initialize()

    # ── Companies ─────────────────────────────────────────────────────────────

    def upsert_companies(self, companies: List[Dict]) -> int:
        """Insert-or-update companies. Returns count of *newly* inserted rows."""
        new_count = 0
        with self._conn() as conn:
            for c in companies:
                if not c.get("name"):
                    continue
                norm = _normalize(c["name"])
                existing = conn.execute(
                    "SELECT id FROM companies WHERE normalized_name = ?", (norm,)
                ).fetchone()
                if existing:
                    # Merge: only overwrite NULL fields
                    conn.execute(
                        """
                        UPDATE companies SET
                            funding_amount = COALESCE(?, funding_amount),
                            funding_round  = COALESCE(?, funding_round),
                            funding_date   = COALESCE(?, funding_date),
                            website        = COALESCE(?, website),
                            description    = COALESCE(?, description),
                            source_url     = COALESCE(?, source_url),
                            updated_at     = CURRENT_TIMESTAMP
                        WHERE normalized_name = ?
                        """,
                        (
                            c.get("funding_amount"), c.get("funding_round"),
                            c.get("funding_date"),   c.get("website"),
                            c.get("description"),    c.get("source_url"),
                            norm,
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO companies
                            (name, normalized_name, description, funding_amount,
                             funding_round, funding_date, website, linkedin_url,
                             crunchbase_url, source, source_url)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            c["name"], norm, c.get("description"),
                            c.get("funding_amount"), c.get("funding_round"),
                            c.get("funding_date"),   c.get("website"),
                            c.get("linkedin_url"),   c.get("crunchbase_url"),
                            c.get("source"),         c.get("source_url"),
                        ),
                    )
                    new_count += 1
        return new_count

    def get_all_companies(self) -> List[Dict]:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM companies ORDER BY name")]

    def get_companies_needing_alumni_search(self, stale_days: int = 7) -> List[Dict]:
        """Companies whose alumni search is absent or older than stale_days."""
        cutoff = (datetime.now() - timedelta(days=stale_days)).isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM companies
                WHERE alumni_searched_at IS NULL OR alumni_searched_at < ?
                ORDER BY created_at DESC
                """,
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_companies_with_contact_count(self) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT c.*, COUNT(ct.id) AS contact_count
                FROM companies c
                LEFT JOIN contacts ct ON ct.company_id = c.id
                GROUP BY c.id
                ORDER BY contact_count DESC, c.name
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def log_alumni_search(self, company_id: int):
        with self._conn() as conn:
            conn.execute(
                "UPDATE companies SET alumni_searched_at = CURRENT_TIMESTAMP WHERE id = ?",
                (company_id,),
            )

    # ── Contacts ──────────────────────────────────────────────────────────────

    def upsert_contacts(self, contacts: List[Dict]) -> int:
        """Insert-or-update contacts. Returns count of *newly* inserted rows."""
        new_count = 0
        with self._conn() as conn:
            for c in contacts:
                if not c.get("name") or not c.get("company_id"):
                    continue
                norm = _normalize(c["name"])
                existing = conn.execute(
                    "SELECT id FROM contacts WHERE company_id = ? AND normalized_name = ?",
                    (c["company_id"], norm),
                ).fetchone()
                if existing:
                    conn.execute(
                        """
                        UPDATE contacts SET
                            email        = COALESCE(?, email),
                            title        = COALESCE(?, title),
                            linkedin_url = COALESCE(?, linkedin_url),
                            updated_at   = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (c.get("email"), c.get("title"), c.get("linkedin_url"), existing["id"]),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO contacts
                            (company_id, name, normalized_name, title, email,
                             linkedin_url, school, source)
                        VALUES (?,?,?,?,?,?,?,?)
                        """,
                        (
                            c["company_id"], c["name"], norm, c.get("title"),
                            c.get("email"), c.get("linkedin_url"),
                            c.get("school", "Stanford GSB"), c.get("source"),
                        ),
                    )
                    new_count += 1
        return new_count

    def get_all_contacts_with_company(self) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT ct.*, co.name AS company_name, co.website AS company_website
                FROM contacts ct
                JOIN companies co ON co.id = ct.company_id
                ORDER BY co.name, ct.name
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def get_contacts_without_email(self, limit: int = 25) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT ct.*, co.website AS company_website, co.name AS company_name
                FROM contacts ct
                JOIN companies co ON co.id = ct.company_id
                WHERE ct.email IS NULL
                ORDER BY ct.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_contact_email(self, contact_id: int, email: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE contacts SET email = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (email, contact_id),
            )
