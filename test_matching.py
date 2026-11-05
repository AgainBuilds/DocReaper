from academic_identity_engine.fingerprints import fingerprint
from academic_identity_engine.matching import CandidateIndex

def test_lsh_returns_exact_duplicate_candidate():
    a = fingerprint("This document describes academic discovery, mathematical fingerprints, and duplicate document detection in a repository.")
    b = fingerprint("This document describes academic discovery, mathematical fingerprints, and duplicate document detection in a repository.")
    index = CandidateIndex()
    index.add("doc-1", a)
    hits = index.query(b)
    assert hits and hits[0]["document_id"] == "doc-1"
    assert hits[0]["normalized_text_match"] is True
