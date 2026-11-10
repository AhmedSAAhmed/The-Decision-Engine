"""Append-only, hash-chained audit log in SQLite.

hash_n = sha256(prev_hash || canonical_json(payload)). Editing any past row breaks every
hash after it, and verify() names the first broken row.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models import AuditRecord

GENESIS = "0" * 64


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def chain_hash(prev: str, payload: dict) -> str:
    return hashlib.sha256((prev + canonical(payload)).encode("utf-8")).hexdigest()


class AuditStore:
    def __init__(self, path: str | Path = ":memory:"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.lock = threading.Lock()
        self.db.execute("""CREATE TABLE IF NOT EXISTS audit (
            seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, ref_id TEXT NOT NULL,
            payload TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL, created_at TEXT NOT NULL)""")
        self.db.execute("CREATE INDEX IF NOT EXISTS audit_ref ON audit(ref_id)")
        self.db.commit()

    def append(self, kind: str, ref_id: str, payload: dict) -> AuditRecord:
        with self.lock:
            row = self.db.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
            prev = row[0] if row else GENESIS
            h = chain_hash(prev, payload)
            now = datetime.now(timezone.utc).isoformat()
            cur = self.db.execute("INSERT INTO audit(kind, ref_id, payload, prev_hash, hash, created_at) VALUES (?,?,?,?,?,?)",
                                  (kind, ref_id, canonical(payload), prev, h, now))
            self.db.commit()
            return AuditRecord(seq=cur.lastrowid, kind=kind, ref_id=ref_id, payload=payload, prev_hash=prev, hash=h, created_at=now)

    def _rows(self, where: str = "", args: tuple = ()) -> list[AuditRecord]:
        q = f"SELECT seq, kind, ref_id, payload, prev_hash, hash, created_at FROM audit {where}"
        return [AuditRecord(seq=s, kind=k, ref_id=r, payload=json.loads(p), prev_hash=ph, hash=h, created_at=c)
                for s, k, r, p, ph, h, c in self.db.execute(q, args).fetchall()]

    def get(self, ref_id: str) -> list[AuditRecord]:
        return self._rows("WHERE ref_id = ? ORDER BY seq", (ref_id,))

    def recent(self, limit: int = 50) -> list[AuditRecord]:
        return self._rows("ORDER BY seq DESC LIMIT ?", (limit,))

    def all(self) -> list[AuditRecord]:
        return self._rows("ORDER BY seq")

    def verify(self) -> tuple[bool, int | None, int]:
        """(ok, first_bad_seq, rows_checked)."""
        prev = GENESIS
        rows = self.db.execute("SELECT seq, payload, prev_hash, hash FROM audit ORDER BY seq").fetchall()
        for seq, payload, prev_hash, h in rows:
            if prev_hash != prev or chain_hash(prev, json.loads(payload)) != h:
                return False, seq, len(rows)
            prev = h
        return True, None, len(rows)
