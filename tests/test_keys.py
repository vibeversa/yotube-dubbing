import pytest

from youtube_dub.providers.keys import ApiKeyPool


def test_api_key_pool_masking():
    pool = ApiKeyPool(["1234567890abcdef"])
    key = pool.get_current_key()
    assert ApiKeyPool._mask_key(key) == "1234...cdef"

    short_pool = ApiKeyPool(["short"])
    assert ApiKeyPool._mask_key(short_pool.get_current_key()) == "***"


def test_api_key_pool_rotation():
    pool = ApiKeyPool(["key1", "key2", "key3"])

    assert pool.get_current_key() == "key1"
    assert not pool.is_exhausted()

    pool.rotate()
    assert pool.get_current_key() == "key2"
    assert not pool.is_exhausted()

    pool.rotate()
    assert pool.get_current_key() == "key3"
    assert not pool.is_exhausted()

    pool.rotate()
    assert pool.is_exhausted()

    with pytest.raises(ValueError, match="No valid API keys remaining"):
        pool.get_current_key()


def test_api_key_pool_empty():
    with pytest.raises(ValueError, match="ApiKeyPool requires at least one API key"):
        ApiKeyPool([])
