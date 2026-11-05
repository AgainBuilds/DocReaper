"""Versioned mathematical fingerprints. Similarity scores are evidence, not identity proofs."""
from __future__ import annotations
import hashlib, re, unicodedata
from dataclasses import dataclass, asdict
from collections import Counter
from typing import Iterable

TOKEN_RE = re.compile(r"[\w]+(?:['’][\w]+)?", re.UNICODE)

@dataclass(frozen=True)
class Fingerprint:
    version: str
    raw_sha256: str
    normalized_sha256: str
    token_count: int
    shingles: tuple[str, ...]
    simhash64: int

    def as_dict(self) -> dict:
        return asdict(self)

def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.replace("\u00ad", "")
    text = re.sub(r"https?://\S+", " URLTOKEN ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(normalize_text(text))

def make_shingles(text: str, k: int = 5) -> tuple[str, ...]:
    words = tokens(text)
    if not words:
        return ()
    if len(words) < k:
        return (" ".join(words),)
    return tuple(sorted({" ".join(words[i:i+k]) for i in range(len(words)-k+1)}))

def _simhash(words: Iterable[str], bits: int = 64) -> int:
    weights = [0] * bits
    counts = Counter(words)
    for token, frequency in counts.items():
        digest = hashlib.blake2b(token.encode(), digest_size=bits // 8).digest()
        value = int.from_bytes(digest, "big")
        for i in range(bits):
            weights[i] += frequency if (value >> i) & 1 else -frequency
    result = 0
    for i, weight in enumerate(weights):
        if weight >= 0:
            result |= 1 << i
    return result

def fingerprint(text: str, raw: bytes | None = None, shingle_size: int = 5) -> Fingerprint:
    normalized = normalize_text(text)
    raw_bytes = raw if raw is not None else text.encode("utf-8")
    words = normalized.split()
    return Fingerprint(
        version="aie-fp-v1",
        raw_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        normalized_sha256=hashlib.sha256(normalized.encode()).hexdigest(),
        token_count=len(words),
        shingles=make_shingles(normalized, shingle_size),
        simhash64=_simhash(words),
    )

def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    aa, bb = set(a), set(b)
    if not aa and not bb: return 1.0
    if not aa or not bb: return 0.0
    return len(aa & bb) / len(aa | bb)

def hamming_distance(a: int, b: int, bits: int = 64) -> int:
    return ((a ^ b) & ((1 << bits) - 1)).bit_count()

def compare(a: Fingerprint, b: Fingerprint) -> dict:
    return {
        "exact_file_match": a.raw_sha256 == b.raw_sha256,
        "normalized_text_match": a.normalized_sha256 == b.normalized_sha256,
        "shingle_jaccard": jaccard(a.shingles, b.shingles),
        "simhash_hamming": hamming_distance(a.simhash64, b.simhash64),
        "token_count_ratio": min(a.token_count, b.token_count) / max(a.token_count, b.token_count, 1),
        "fingerprint_version": a.version if a.version == b.version else "incompatible",
    }

def minhash_signature(shingles: Iterable[str], num_perm: int = 128) -> tuple[int, ...]:
    """Deterministic MinHash signature using independent seeded BLAKE2b hashes."""
    values = tuple(shingles)
    if not values: return tuple([2**64 - 1] * num_perm)
    signature = []
    for seed in range(num_perm):
        prefix = seed.to_bytes(4, "big")
        signature.append(min(int.from_bytes(hashlib.blake2b(prefix + item.encode("utf-8"), digest_size=8).digest(), "big") for item in values))
    return tuple(signature)

def minhash_band_keys(signature: Iterable[int], bands: int = 16) -> tuple[str, ...]:
    sig = tuple(signature)
    if len(sig) % bands: raise ValueError("signature length must be divisible by bands")
    width = len(sig) // bands
    return tuple(f"{band}:" + ":".join(f"{x:016x}" for x in sig[band*width:(band+1)*width]) for band in range(bands))
