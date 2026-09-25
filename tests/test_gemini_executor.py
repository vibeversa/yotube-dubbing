import asyncio

import pytest

from youtube_dub.domain.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderInvalidRequestError,
    ProviderQuotaError,
    ProviderTransientError,
)
from youtube_dub.providers.gemini.executor import GeminiCallExecutor
from youtube_dub.providers.keys import ApiKeyPool


# A fake sleeper that doesn't actually sleep
async def fake_sleep(delay: float) -> None:
    pass


@pytest.fixture
def key_pool():
    return ApiKeyPool(["key1", "key2"])


@pytest.fixture
def executor(key_pool):
    return GeminiCallExecutor(
        models=["modelA", "modelB"],
        key_pool=key_pool,
        max_attempts=3,
        sleeper=fake_sleep,
    )


@pytest.mark.asyncio
async def test_successful_execution(executor):
    calls = []

    async def op(model, key):
        calls.append((model, key))
        return "success"

    res = await executor.execute(op)
    assert res == "success"
    assert calls == [("modelA", "key1")]


@pytest.mark.asyncio
async def test_quota_rotates_key(executor):
    calls = []

    async def op(model, key):
        calls.append((model, key))
        if key == "key1":
            raise ProviderQuotaError("Quota exceeded")
        return "success2"

    res = await executor.execute(op)
    assert res == "success2"
    assert calls == [("modelA", "key1"), ("modelA", "key2")]


@pytest.mark.asyncio
async def test_transient_retries_and_falls_back(executor):
    calls = []

    async def op(model, key):
        calls.append((model, key))
        if model == "modelA":
            raise ProviderTransientError("Temporary timeout")
        return "successB"

    res = await executor.execute(op)
    assert res == "successB"
    # Should try modelA 3 times (max_attempts) with round-robined keys, then fall back to modelB
    assert calls == [
        ("modelA", "key1"),
        ("modelA", "key2"),
        ("modelA", "key1"),
        ("modelB", "key2"),
    ]


@pytest.mark.asyncio
async def test_invalid_request_fails_fast(executor):
    async def op(model, key):
        raise ProviderInvalidRequestError("Bad prompt")

    with pytest.raises(ProviderInvalidRequestError):
        await executor.execute(op)


@pytest.mark.asyncio
async def test_all_keys_and_models_exhausted(executor):
    async def op(model, key):
        raise ProviderQuotaError("Out of quota")

    with pytest.raises(ProviderError, match="All models and keys exhausted"):
        await executor.execute(op)


@pytest.mark.asyncio
async def test_cancellation(executor):
    async def op(model, key):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await executor.execute(op)


@pytest.mark.asyncio
async def test_authentication_invalidates_key_globally(executor, key_pool):
    calls = []

    async def op(model, key):
        calls.append((model, key))
        if key == "key1":
            raise ProviderAuthenticationError("Invalid API key")
        return "success_auth"

    res = await executor.execute(op)
    assert res == "success_auth"
    assert calls == [("modelA", "key1"), ("modelA", "key2")]

    # Key1 should be globally removed
    assert key_pool.get_all_keys() == ["key2"]


@pytest.mark.asyncio
async def test_quota_error_model_fallback(key_pool):
    # Test that if a single run hits quota for ALL keys on modelA, it falls back to modelB
    executor = GeminiCallExecutor(
        models=["modelA", "modelB"],
        key_pool=key_pool,
        max_attempts=3,
        sleeper=fake_sleep,
    )

    calls = []

    async def op(model, key):
        calls.append((model, key))
        if model == "modelA":
            raise ProviderQuotaError("Rate limit on modelA")
        return "success_fallback"

    res = await executor.execute(op)
    assert res == "success_fallback"

    # modelA hits quota on key1, then on key2, then all keys are tried for this run, so it falls back to modelB
    assert calls == [
        ("modelA", "key1"),
        ("modelA", "key2"),
        ("modelB", "key1"),
    ]


@pytest.mark.asyncio
async def test_concurrent_execution_does_not_poison_pool(key_pool):
    executor = GeminiCallExecutor(
        models=["modelA", "modelB"],
        key_pool=key_pool,
        max_attempts=3,
        sleeper=fake_sleep,
    )

    # Simulate two concurrent tasks. Task 1 hits quota limit on all keys for modelA,
    # falling back to modelB. Task 2 comes in afterwards (or concurrently) and uses keys freely on modelA again.

    calls = []

    async def op_fail_a(model, key):
        calls.append(("fail_a", model, key))
        if model == "modelA":
            raise ProviderQuotaError("Quota limit")
        return "fallback_success"

    async def op_success_a(model, key):
        calls.append(("success_a", model, key))
        return "success"

    res1 = await executor.execute(op_fail_a)
    assert res1 == "fallback_success"

    res2 = await executor.execute(op_success_a)
    assert res2 == "success"

    assert key_pool.has_keys()

    # The first task tried all keys on modelA and fell back.
    # The second task could still use modelA and key1 because the key pool wasn't globally poisoned by quota errors.
    assert calls == [
        ("fail_a", "modelA", "key1"),
        ("fail_a", "modelA", "key2"),
        ("fail_a", "modelB", "key1"),
        ("success_a", "modelA", "key2"),  # round robin points to key2 next
    ]
