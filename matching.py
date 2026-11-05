"""Pure-Python MinHash + banded LSH candidate index.

This implementation is dependency-light and deterministic. It is in-memory; use a
persistent key/value or database-backed bucket store for multi-worker production.
"""
from __future__ import annotations
from collections import defaultdict
from .fingerprints import Fingerprint, compare, minhash_signature, minhash_band_keys

class CandidateIndex:
    def __init__(self, threshold: float = 0.75, num_perm: int = 128, bands: int = 16):
        if not 0 < threshold <= 1: raise ValueError("threshold must be in (0, 1]")
        if num_perm % bands: raise ValueError("num_perm must be divisible by bands")
        self.threshold, self.num_perm, self.bands = threshold, num_perm, bands
        self.rows_per_band = num_perm // bands
        self.profiles: dict[str, Fingerprint] = {}
        self.buckets: dict[tuple[int, tuple[int, ...]], set[str]] = defaultdict(set)

    def _keys(self, profile: Fingerprint):
        signature = minhash_signature(profile.shingles, self.num_perm)
        keys = minhash_band_keys(signature, self.bands)
        return tuple((i, key) for i, key in enumerate(keys))

    def add(self, document_id: str, profile: Fingerprint) -> None:
        if document_id in self.profiles: return
        for key in self._keys(profile): self.buckets[key].add(document_id)
        self.profiles[document_id] = profile

    def query(self, profile: Fingerprint, limit: int = 20) -> list[dict]:
        candidates: set[str] = set()
        for key in self._keys(profile): candidates.update(self.buckets.get(key, ()))
        rows = [{"document_id": i, **compare(profile, self.profiles[i])} for i in candidates]
        rows.sort(key=lambda x: (x["normalized_text_match"], x["shingle_jaccard"], -x["simhash_hamming"]), reverse=True)
        return rows[:limit]
