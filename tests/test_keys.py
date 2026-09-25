import pytest

from youtube_dub.providers.keys import ApiKeyPool


def test_api_key_pool_masking():
    pool = ApiKeyPool(["1234567890abcdef"])
    key = pool.get_next_key()
    assert ApiKeyPool._mask_key(key) == "1234...cdef"

    short_pool = ApiKeyPool(["short"])
    assert ApiKeyPool._mask_key(short_pool.get_next_key()) == "***"


def test_api_key_pool_round_robin():
    pool = ApiKeyPool(["key1", "key2", "key3"])

    assert pool.has_keys()

    assert pool.get_next_key() == "key1"
    assert pool.get_next_key() == "key2"
    assert pool.get_next_key() == "key3"

    # Wraps around
    assert pool.get_next_key() == "key1"


def test_api_key_pool_invalidation():
    pool = ApiKeyPool(["key1", "key2", "key3"])

    # First access moves the internal index to 1
    assert pool.get_next_key() == "key1"

    pool.invalidate_key("key2")
    assert pool.has_keys()

    # Index is now 1, but 'key2' was at index 1, and now 'key3' is at index 1
    assert pool.get_next_key() == "key3"
    assert pool.get_next_key() == "key1"

    pool.invalidate_key("key1")
    pool.invalidate_key("key3")

    assert not pool.has_keys()

    with pytest.raises(ValueError, match="No valid API keys remaining"):
        pool.get_next_key()


def test_api_key_pool_empty():
    with pytest.raises(ValueError, match="ApiKeyPool requires at least one API key"):
        ApiKeyPool([])
