from academic_identity_engine.storage import Store
from academic_identity_engine.fingerprints import fingerprint

def test_store_deduplicates_normalized_text(tmp_path):
    store = Store(f"sqlite:///{tmp_path/'test.db'}")
    text = "This is a sufficiently long academic text to pass the minimum indexing threshold."
    a, dup_a = store.add_document(text, fingerprint(text), title="Paper A")
    b, dup_b = store.add_document(text, fingerprint(text), title="Paper B", url="https://example.org/paper", source_name="test")
    assert dup_a is None
    assert dup_b == a["id"]
    assert b["id"] == a["id"]
    assert store.stats()["documents"] == 1
    assert store.stats()["sources"] == 1
