from academic_identity_engine.fingerprints import fingerprint, jaccard, hamming_distance, normalize_text

def test_normalization_equivalence():
    assert normalize_text("HELLO   World") == normalize_text("hello world")

def test_exact_text_identity():
    a = fingerprint("The same academic document contains enough words to be indexed accurately.")
    b = fingerprint("The same academic document contains enough words to be indexed accurately.")
    assert a.normalized_sha256 == b.normalized_sha256
    assert a.raw_sha256 == b.raw_sha256

def test_formatting_tolerant_identity():
    a = fingerprint("A useful research paper with a title and several paragraphs of content.")
    b = fingerprint("A USEFUL research paper with a title and several paragraphs of content.")
    assert a.normalized_sha256 == b.normalized_sha256

def test_jaccard():
    assert jaccard(["a", "b"], ["b", "c"]) == 1/3
    assert jaccard([], []) == 1.0

def test_hamming():
    assert hamming_distance(0b1010, 0b1001) == 2
