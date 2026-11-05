import pytest
from academic_identity_engine.network import validate_public_url, UnsafeURL

def test_rejects_http():
    with pytest.raises(UnsafeURL): validate_public_url("http://example.org")

def test_rejects_localhost():
    with pytest.raises(UnsafeURL): validate_public_url("https://localhost/private")
