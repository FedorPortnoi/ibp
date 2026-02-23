"""
Local Leak Database Sources
============================
Queries local SQLite database built from imported CSV leak dumps.

Sources:
- VK2012LeakSource: 100M records from 2012 VK.com breach
- GetContactLeakSource: GetContact crowdsourced contacts dump
- TelcoLeakSource: Beeline/MTS subscriber data leaks

All sources share a single LeakDB backend for efficient querying.
Data is loaded via scripts/load_leaks.py CLI tool.

Tier: S (Breach Database) — real data from confirmed leaks
"""

import json
import logging
import os
import sqlite3
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from app.utils.phone import normalize_phone

from ..base_source import BaseSource, SourceResult, SourceTier, SourceType

logger = logging.getLogger(__name__)

# Default database path (project_root/data/leaks/all_leaks.db)
_PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')
)
DEFAULT_DB_PATH = os.path.join(_PROJECT_ROOT, 'data', 'leaks', 'all_leaks.db')


# ---------------------------------------------------------------------------
# In-memory LRU cache (no Redis dependency)
# ---------------------------------------------------------------------------

class _LRUCache:
    """Thread-safe LRU cache for hot leak queries."""

    def __init__(self, maxsize: int = 50_000):
        self._cache: OrderedDict = OrderedDict()
        self._maxsize = maxsize
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self._maxsize:
                    self._cache.popitem(last=False)
            self._cache[key] = value

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


_leak_cache = _LRUCache()


# ---------------------------------------------------------------------------
# LeakDB — SQLite wrapper
# ---------------------------------------------------------------------------

class LeakDB:
    """
    SQLite wrapper for the local leak database.

    Thread-safe (thread-local connections), WAL mode for concurrent reads.

    Schema::

        leak_records(
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            phone       TEXT,           -- +7XXXXXXXXXX canonical
            email       TEXT,
            name        TEXT,
            username    TEXT,
            address     TEXT,
            passport    TEXT,
            password_hash TEXT,
            source      TEXT NOT NULL,   -- 'vk_2012', 'getcontact', 'telco'
            confidence  REAL DEFAULT 0.85,
            extra       TEXT             -- JSON blob for source-specific fields
        )
    """

    _instance: Optional['LeakDB'] = None
    _instance_lock = threading.Lock()

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = os.path.normpath(db_path or DEFAULT_DB_PATH)
        self._local = threading.local()
        self._ensure_schema()

    # -- singleton ------------------------------------------------------------

    @classmethod
    def get_instance(cls, db_path: Optional[str] = None) -> 'LeakDB':
        """Return the module-wide singleton, creating it on first call."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls(db_path)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Drop the singleton (useful for tests)."""
        with cls._instance_lock:
            cls._instance = None
        _leak_cache.clear()

    # -- connection -----------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            # SQLite LOWER() is ASCII-only; register Unicode-aware version
            conn.create_function('ULOWER', 1, lambda s: s.lower() if s else s)
            self._local.conn = conn
        return conn

    def _ensure_schema(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS leak_records (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                phone         TEXT,
                email         TEXT,
                name          TEXT,
                username      TEXT,
                address       TEXT,
                passport      TEXT,
                password_hash TEXT,
                source        TEXT NOT NULL,
                confidence    REAL DEFAULT 0.85,
                extra         TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_leak_phone    ON leak_records(phone);
            CREATE INDEX IF NOT EXISTS idx_leak_email    ON leak_records(email);
            CREATE INDEX IF NOT EXISTS idx_leak_name     ON leak_records(name);
            CREATE INDEX IF NOT EXISTS idx_leak_username  ON leak_records(username);
            CREATE INDEX IF NOT EXISTS idx_leak_source   ON leak_records(source);
        """)

    # -- queries --------------------------------------------------------------

    def query_phone(self, phone: str, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Look up records by normalized phone number."""
        normalized = normalize_phone(phone)
        if not normalized or not normalized.startswith('+7'):
            return []

        cache_key = f"phone:{normalized}:{source or '*'}"
        cached = _leak_cache.get(cache_key)
        if cached is not None:
            return cached

        conn = self._get_conn()
        if source:
            rows = conn.execute(
                "SELECT * FROM leak_records WHERE phone = ? AND source = ?",
                (normalized, source),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM leak_records WHERE phone = ?",
                (normalized,),
            ).fetchall()

        results = [dict(r) for r in rows]
        _leak_cache.set(cache_key, results)
        return results

    def query_email(self, email: str, source: Optional[str] = None) -> List[Dict[str, Any]]:
        if not email:
            return []
        email_low = email.lower().strip()

        cache_key = f"email:{email_low}:{source or '*'}"
        cached = _leak_cache.get(cache_key)
        if cached is not None:
            return cached

        conn = self._get_conn()
        if source:
            rows = conn.execute(
                "SELECT * FROM leak_records WHERE ULOWER(email) = ? AND source = ?",
                (email_low, source),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM leak_records WHERE ULOWER(email) = ?",
                (email_low,),
            ).fetchall()

        results = [dict(r) for r in rows]
        _leak_cache.set(cache_key, results)
        return results

    def query_name(self, name: str, source: Optional[str] = None) -> List[Dict[str, Any]]:
        if not name:
            return []
        name_low = name.lower().strip()

        cache_key = f"name:{name_low}:{source or '*'}"
        cached = _leak_cache.get(cache_key)
        if cached is not None:
            return cached

        conn = self._get_conn()
        if source:
            rows = conn.execute(
                "SELECT * FROM leak_records WHERE ULOWER(name) = ? AND source = ?",
                (name_low, source),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM leak_records WHERE ULOWER(name) = ?",
                (name_low,),
            ).fetchall()

        results = [dict(r) for r in rows]
        _leak_cache.set(cache_key, results)
        return results

    def query_username(self, username: str, source: Optional[str] = None) -> List[Dict[str, Any]]:
        if not username:
            return []
        uname_low = username.lower().strip()

        cache_key = f"username:{uname_low}:{source or '*'}"
        cached = _leak_cache.get(cache_key)
        if cached is not None:
            return cached

        conn = self._get_conn()
        if source:
            rows = conn.execute(
                "SELECT * FROM leak_records WHERE ULOWER(username) = ? AND source = ?",
                (uname_low, source),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM leak_records WHERE ULOWER(username) = ?",
                (uname_low,),
            ).fetchall()

        results = [dict(r) for r in rows]
        _leak_cache.set(cache_key, results)
        return results

    # -- mutations (used by the loader script) --------------------------------

    def insert_batch(self, records: List[Dict[str, Any]], batch_size: int = 5000) -> int:
        """Bulk-insert records. Returns number of rows inserted."""
        conn = self._get_conn()
        sql = """INSERT INTO leak_records
                 (phone, email, name, username, address, passport,
                  password_hash, source, confidence, extra)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        total = 0
        batch: list = []
        for rec in records:
            batch.append((
                rec.get('phone'),
                rec.get('email'),
                rec.get('name'),
                rec.get('username'),
                rec.get('address'),
                rec.get('passport'),
                rec.get('password_hash'),
                rec['source'],
                rec.get('confidence', 0.85),
                json.dumps(rec['extra'], ensure_ascii=False) if rec.get('extra') else None,
            ))
            if len(batch) >= batch_size:
                conn.executemany(sql, batch)
                conn.commit()
                total += len(batch)
                batch = []
        if batch:
            conn.executemany(sql, batch)
            conn.commit()
            total += len(batch)
        return total

    def count(self, source: Optional[str] = None) -> int:
        conn = self._get_conn()
        if source:
            row = conn.execute(
                "SELECT COUNT(*) FROM leak_records WHERE source = ?", (source,)
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) FROM leak_records").fetchone()
        return row[0]

    @property
    def exists(self) -> bool:
        if not os.path.isfile(self.db_path):
            return False
        try:
            return self.count() > 0
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Helper: convert a DB row dict → list of SourceResult
# ---------------------------------------------------------------------------

def _row_to_results(
    hit: Dict[str, Any],
    source_name: str,
    source_tier: SourceTier,
    source_tag: str,
    query_key: str,
    seen: set,
    extra_meta: Optional[Dict] = None,
) -> List[SourceResult]:
    """Shared converter used by all leak sources."""
    results: List[SourceResult] = []
    conf = hit.get('confidence', 0.85)
    base_meta = {'leak_source': source_tag, 'queried_by': query_key}
    if extra_meta:
        base_meta.update(extra_meta)

    def _emit(data_type: str, value: str, confidence: float = conf,
              verified: bool = False, raw: Optional[Dict] = None,
              meta: Optional[Dict] = None):
        key = f"{data_type}:{value.lower().strip()}"
        if key in seen:
            return
        seen.add(key)
        m = dict(base_meta)
        if meta:
            m.update(meta)
        results.append(SourceResult(
            data_type=data_type,
            value=value,
            source_name=source_name,
            source_tier=source_tier,
            confidence=confidence,
            verified=verified,
            raw_data=raw or {},
            metadata=m,
        ))

    if hit.get('name'):
        _emit('name', hit['name'])
    if hit.get('email'):
        _emit('email', hit['email'])
    if hit.get('phone'):
        _emit('phone', hit['phone'])
    if hit.get('username'):
        _emit('username', hit['username'], confidence=conf * 0.9)
    if hit.get('address'):
        _emit('address', hit['address'], confidence=0.90)
    if hit.get('passport'):
        _emit('passport', hit['passport'], confidence=0.95, verified=True,
              meta={'masked': '****' in hit['passport']})
    if hit.get('password_hash'):
        ident = hit.get('email') or hit.get('username') or 'unknown'
        _emit('credential', ident, raw={'password_hash': hit['password_hash']},
              meta={'hash_type': 'md5'})

    return results


# ---------------------------------------------------------------------------
# VK2012LeakSource
# ---------------------------------------------------------------------------

class VK2012LeakSource(BaseSource):
    """
    VK.com 2012 breach — ~100M records.

    Fields: phone, email, username -> name, password_hash
    Tier: S (Breach Database)
    """

    name = "VK 2012 Leak"
    source_type = SourceType.IDENTITY
    source_tier = SourceTier.S
    requires_api_key = False
    rate_limit_per_minute = 1000

    SOURCE_TAG = 'vk_2012'

    def __init__(self):
        super().__init__()
        self._db = LeakDB.get_instance()

    def is_available(self) -> bool:
        try:
            return self._db.exists and self._db.count(self.SOURCE_TAG) > 0
        except Exception:
            return False

    def query_impl(
        self,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None,
        vk_id: Optional[str] = None,
        photo_path: Optional[str] = None,
        **kwargs,
    ) -> List[SourceResult]:
        results: List[SourceResult] = []
        seen: set = set()
        extra = {'breach_year': 2012}

        if phone:
            hits = self._db.query_phone(phone, source=self.SOURCE_TAG)
            self.logger.info(f"leakdb: {phone} -> {len(hits)} hits (vk_2012/phone)")
            for h in hits:
                results.extend(_row_to_results(
                    h, self.name, self.source_tier, self.SOURCE_TAG,
                    f"phone:{phone}", seen, extra,
                ))

        if email:
            emails = [email] if isinstance(email, str) else list(email)
            for em in emails[:5]:
                hits = self._db.query_email(em, source=self.SOURCE_TAG)
                self.logger.info(f"leakdb: {em} -> {len(hits)} hits (vk_2012/email)")
                for h in hits:
                    results.extend(_row_to_results(
                        h, self.name, self.source_tier, self.SOURCE_TAG,
                        f"email:{em}", seen, extra,
                    ))

        if username:
            hits = self._db.query_username(username, source=self.SOURCE_TAG)
            self.logger.info(f"leakdb: {username} -> {len(hits)} hits (vk_2012/username)")
            for h in hits:
                results.extend(_row_to_results(
                    h, self.name, self.source_tier, self.SOURCE_TAG,
                    f"username:{username}", seen, extra,
                ))

        return results


# ---------------------------------------------------------------------------
# GetContactLeakSource
# ---------------------------------------------------------------------------

class GetContactLeakSource(BaseSource):
    """
    GetContact crowdsourced contacts dump (offline).

    Fields: phone -> names[], tags[]
    Tier: S (Breach Database)

    Separate from the API-based GetContactSource in getcontact.py.
    """

    name = "GetContact Leak DB"
    source_type = SourceType.IDENTITY
    source_tier = SourceTier.S
    requires_api_key = False
    rate_limit_per_minute = 1000

    SOURCE_TAG = 'getcontact'

    def __init__(self):
        super().__init__()
        self._db = LeakDB.get_instance()

    def is_available(self) -> bool:
        try:
            return self._db.exists and self._db.count(self.SOURCE_TAG) > 0
        except Exception:
            return False

    def query_impl(
        self,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None,
        vk_id: Optional[str] = None,
        photo_path: Optional[str] = None,
        **kwargs,
    ) -> List[SourceResult]:
        if not phone:
            return []

        hits = self._db.query_phone(phone, source=self.SOURCE_TAG)
        self.logger.info(f"leakdb: {phone} -> {len(hits)} hits (getcontact)")
        if not hits:
            return []

        # Collect unique names and tags across all matching records
        names: List[str] = []
        tags: List[str] = []
        for hit in hits:
            if hit.get('name') and hit['name'] not in names:
                names.append(hit['name'])
            extra = _parse_extra(hit)
            for t in extra.get('tags', []):
                if t not in tags:
                    tags.append(t)

        results: List[SourceResult] = []

        # Emit name results (first name = highest confidence)
        for i, cname in enumerate(names[:10]):
            results.append(SourceResult(
                data_type='name',
                value=cname,
                source_name=self.name,
                source_tier=self.source_tier,
                confidence=max(0.50, 0.85 - i * 0.05),
                metadata={
                    'leak_source': self.SOURCE_TAG,
                    'name_rank': i + 1,
                    'total_names': len(names),
                    'tag_count': len(tags),
                },
            ))

        # Emit tags as profile metadata
        if tags:
            results.append(SourceResult(
                data_type='profile',
                value=phone,
                source_name=self.name,
                source_tier=self.source_tier,
                confidence=0.80,
                raw_data={'tags': tags, 'names': names},
                metadata={
                    'leak_source': self.SOURCE_TAG,
                    'tag_count': len(tags),
                    'name_count': len(names),
                },
            ))

        return results


# ---------------------------------------------------------------------------
# TelcoLeakSource
# ---------------------------------------------------------------------------

class TelcoLeakSource(BaseSource):
    """
    Telecom subscriber data leaks (Beeline, MTS, Megafon, etc.).

    Fields: phone -> passport, full_name, address, subscriber_since
    Tier: S (Breach Database) — passport data is identity gold standard.

    CSV row example:
        +79123456789,**** **** 12 345678,Иванов Иван Иванович,Москва ул Ленина 15,2020-01-01
    """

    name = "Telco Leak DB"
    source_type = SourceType.IDENTITY
    source_tier = SourceTier.S
    requires_api_key = False
    rate_limit_per_minute = 1000

    SOURCE_TAG = 'telco'

    def __init__(self):
        super().__init__()
        self._db = LeakDB.get_instance()

    def is_available(self) -> bool:
        try:
            return self._db.exists and self._db.count(self.SOURCE_TAG) > 0
        except Exception:
            return False

    def query_impl(
        self,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None,
        vk_id: Optional[str] = None,
        photo_path: Optional[str] = None,
        **kwargs,
    ) -> List[SourceResult]:
        if not phone:
            return []

        hits = self._db.query_phone(phone, source=self.SOURCE_TAG)
        self.logger.info(f"leakdb: {phone} -> {len(hits)} hits (telco)")

        results: List[SourceResult] = []
        seen: set = set()

        for hit in hits:
            extra = _parse_extra(hit)

            results.extend(_row_to_results(
                hit, self.name, self.source_tier, self.SOURCE_TAG,
                f"phone:{phone}", seen,
                extra_meta={
                    'data_quality': 'telco_subscriber',
                    'carrier': extra.get('carrier', 'unknown'),
                },
            ))

            # subscriber_since lives in extra
            if extra.get('subscriber_since'):
                results.append(SourceResult(
                    data_type='profile',
                    value=phone,
                    source_name=self.name,
                    source_tier=self.source_tier,
                    confidence=0.90,
                    metadata={
                        'leak_source': self.SOURCE_TAG,
                        'subscriber_since': extra['subscriber_since'],
                        'carrier': extra.get('carrier', 'unknown'),
                    },
                ))

        return results


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _parse_extra(hit: Dict[str, Any]) -> Dict[str, Any]:
    """Safely parse the JSON `extra` column."""
    raw = hit.get('extra')
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
