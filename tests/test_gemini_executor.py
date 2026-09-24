import asyncio

import pytest

from youtube_dub.domain.errors import (
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
    # Should try modelA 3 times (max_attempts) with same key, then fall back to modelB
    assert calls == [
        ("modelA", "key1"),
        ("modelA", "key1"),
        ("modelA", "key1"),
        ("modelB", "key1"),
    ]


@pytest.mark.asyncio
async def test_invalid_request_fails_fast(executor):
    async def op(model, key):
        raise ProviderInvalidRequestError("Bad prompt")

    with pytest.raises(ProviderInvalidRequestError):
        await executor.execute(op)


@pytest.mark.asyncio
async def test_all_keys_and_models_exhausted():
    pool = ApiKeyPool(["key1"])
    executor = GeminiCallExecutor(["modelA", "modelB"], pool, sleeper=fake_sleep)

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
