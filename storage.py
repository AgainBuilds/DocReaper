"""SQLite persistence with source-level provenance and indexed hashes."""
import json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from .fingerprints import Fingerprint, minhash_signature, minhash_band_keys

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS documents (
 id TEXT PRIMARY KEY, title TEXT, canonical_hash TEXT NOT NULL, text_hash TEXT NOT NULL,
 simhash TEXT NOT NULL, token_count INTEGER NOT NULL, text TEXT NOT NULL, format TEXT NOT NULL,
 language TEXT, metadata_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_docs_raw ON documents(canonical_hash);
CREATE INDEX IF NOT EXISTS ix_docs_text ON documents(text_hash);
CREATE TABLE IF NOT EXISTS sources (
 id INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT NOT NULL REFERENCES documents(id),
 url TEXT, source_name TEXT NOT NULL, rights_status TEXT NOT NULL, discovered_at TEXT NOT NULL,
 metadata_json TEXT NOT NULL, UNIQUE(document_id,url)
);
CREATE INDEX IF NOT EXISTS ix_sources_url ON sources(url);
CREATE TABLE IF NOT EXISTS lsh_buckets (bucket_key TEXT NOT NULL, document_id TEXT NOT NULL REFERENCES documents(id), PRIMARY KEY(bucket_key,document_id));
CREATE INDEX IF NOT EXISTS ix_lsh_bucket ON lsh_buckets(bucket_key);
CREATE TABLE IF NOT EXISTS discovery_records (
 id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL UNIQUE, title TEXT, source_name TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'discovered', discovered_at TEXT NOT NULL, metadata_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS crawl_jobs (
 id TEXT PRIMARY KEY, job_type TEXT NOT NULL, status TEXT NOT NULL, total INTEGER DEFAULT 0,
 completed INTEGER DEFAULT 0, failed INTEGER DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 details_json TEXT NOT NULL
);
"""

class Store:
    def __init__(self, url: str = "sqlite:///./aie.db"):
        if url.startswith("sqlite+aiosqlite:///"): url = url.replace("sqlite+aiosqlite:///", "sqlite:///", 1)
        if not url.startswith("sqlite:///"): raise ValueError("This bundled Store currently requires SQLite. PostgreSQL adapter is a deployment extension.")
        self.path = url.removeprefix("sqlite:///")
        if self.path != ":memory:": Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self): self.conn.close()

    def add_document(self, text: str, profile: Fingerprint, title=None, fmt="text", language=None, metadata=None, url=None, source_name="manual", rights_status="unknown"):
        cur = self.conn.cursor()
        row = cur.execute("SELECT id FROM documents WHERE canonical_hash=? OR text_hash=? LIMIT 1", (profile.raw_sha256, profile.normalized_sha256)).fetchone()
        duplicate_of = row["id"] if row else None
        doc_id = duplicate_of or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        if not duplicate_of:
            cur.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?)", (doc_id,title,profile.raw_sha256,profile.normalized_sha256,str(profile.simhash64),profile.token_count,text,fmt,language,json.dumps(metadata or {}),now))
            signature = minhash_signature(profile.shingles)
            cur.executemany("INSERT OR IGNORE INTO lsh_buckets(bucket_key,document_id) VALUES(?,?)", [(key, doc_id) for key in minhash_band_keys(signature)])
        if url:
            cur.execute("INSERT OR IGNORE INTO sources(document_id,url,source_name,rights_status,discovered_at,metadata_json) VALUES(?,?,?,?,?,?)", (doc_id,str(url),source_name,rights_status,now,json.dumps({"duplicate_observed": bool(duplicate_of)})))
        self.conn.commit()
        return self.get_document(doc_id), duplicate_of

    def get_document(self, doc_id):
        row = self.conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not row: return None
        result = dict(row); result["metadata"] = json.loads(result.pop("metadata_json"))
        result["sources"] = [dict(x) for x in self.conn.execute("SELECT url,source_name,rights_status,discovered_at FROM sources WHERE document_id=?",(doc_id,))]
        return result

    def list_documents(self, q=None, limit=25, offset=0):
        if q:
            rows = self.conn.execute("SELECT id,title,canonical_hash,text_hash,format,created_at FROM documents WHERE title LIKE ? OR text LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?",(f"%{q}%",f"%{q}%",limit,offset))
        else:
            rows = self.conn.execute("SELECT id,title,canonical_hash,text_hash,format,created_at FROM documents ORDER BY created_at DESC LIMIT ? OFFSET ?",(limit,offset))
        return [dict(r) for r in rows]

    def candidate_fingerprints(self, profile: Fingerprint, limit: int = 500):
        keys = minhash_band_keys(minhash_signature(profile.shingles))
        placeholders = ",".join("?" for _ in keys)
        return self.conn.execute(
            f"SELECT d.id,d.title,d.text,d.canonical_hash,d.text_hash,d.simhash,d.token_count,COUNT(*) AS collisions "
            f"FROM lsh_buckets b JOIN documents d ON d.id=b.document_id WHERE b.bucket_key IN ({placeholders}) "
            f"GROUP BY d.id ORDER BY collisions DESC LIMIT ?", (*keys, limit)
        ).fetchall()

    def add_discovery(self, url, title, source, metadata=None):
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute("INSERT OR IGNORE INTO discovery_records(url,title,source_name,discovered_at,metadata_json) VALUES(?,?,?,?,?)",(str(url),title,source,now,json.dumps(metadata or {})))
        self.conn.commit()

    def discovery_queue(self, limit=100):
        return [dict(r) for r in self.conn.execute("SELECT * FROM discovery_records WHERE status='discovered' LIMIT ?",(limit,))]

    def set_discovery_status(self, url, status):
        self.conn.execute("UPDATE discovery_records SET status=? WHERE url=?",(status,url)); self.conn.commit()

    def stats(self):
        return {"documents": self.conn.execute("SELECT count(*) FROM documents").fetchone()[0], "sources": self.conn.execute("SELECT count(*) FROM sources").fetchone()[0], "discovered_urls": self.conn.execute("SELECT count(*) FROM discovery_records").fetchone()[0]}
