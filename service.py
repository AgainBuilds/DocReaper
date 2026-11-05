import base64
from .fingerprints import fingerprint, compare
from .extraction import extract_bytes
from .network import fetch_url
from .storage import Store
from .matching import CandidateIndex

class Engine:
    def __init__(self, store: Store): self.store = store

    def ingest_text(self, text: str, title=None, url=None, source_name="manual", rights_status="unknown", language=None, metadata=None, raw=None, fmt="text"):
        if len(text.strip()) < 40: raise ValueError("Extracted text is too short to index (minimum 40 characters)")
        profile = fingerprint(text, raw=raw)
        doc, duplicate_of = self.store.add_document(text, profile, title, fmt, language, metadata, url, source_name, rights_status)
        return {"document": doc, "duplicate_of": duplicate_of, "fingerprint": profile.as_dict()}

    async def ingest_url(self, url: str, title=None, source_name="web", rights_status="unknown"):
        data, ctype, final_url = await fetch_url(url)
        text, fmt, extracted_meta = extract_bytes(data, final_url, ctype)
        return self.ingest_text(text, title=title or extracted_meta.get("title") or extracted_meta.get("html_title"), url=final_url, source_name=source_name, rights_status=rights_status, metadata={"extraction": extracted_meta, "content_type": ctype}, raw=data, fmt=fmt.value)

    def ingest_base64(self, encoded: str, filename: str, title=None, source_name="upload", rights_status="unknown"):
        data = base64.b64decode(encoded, validate=True)
        text, fmt, meta = extract_bytes(data, filename)
        return self.ingest_text(text, title=title or filename, source_name=source_name, rights_status=rights_status, metadata=meta, raw=data, fmt=fmt.value)

    def similar(self, text: str, limit=10):
        query = fingerprint(text)
        rows = []
        for row in self.store.candidate_fingerprints(query, limit=max(500, limit * 20)):
            candidate = fingerprint(row["text"])
            scores = compare(query, candidate)
            score = max(scores["shingle_jaccard"], 1.0 if scores["normalized_text_match"] else 0.0)
            if score > 0.05 or scores["simhash_hamming"] <= 12:
                rows.append({"id": row["id"], "title": row["title"], "score": score, "lsh_collisions": row["collisions"], **scores})
        rows.sort(key=lambda r: (r["normalized_text_match"], r["shingle_jaccard"], -r["simhash_hamming"]), reverse=True)
        return rows[:limit]
