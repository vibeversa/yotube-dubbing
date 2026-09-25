import asyncio
import logging
import random
from collections.abc import Callable, Coroutine
from typing import Any

from youtube_dub.domain.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderInvalidRequestError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderTransientError,
)
from youtube_dub.providers.keys import ApiKeyPool

logger = logging.getLogger(__name__)


class GeminiCallExecutor:
    def __init__(
        self,
        models: list[str],
        key_pool: ApiKeyPool,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 10.0,
        jitter: float = 0.1,
        sleeper: Callable[[float], Coroutine[Any, Any, None]] = asyncio.sleep,
    ):
        if not models:
            raise ValueError("GeminiCallExecutor requires at least one model")

        self.models = models
        self.key_pool = key_pool
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self._sleep = sleeper

    async def execute(
        self, operation: Callable[[str, str], Coroutine[Any, Any, Any]]
    ) -> Any:
        """
        Executes an operation across configured models and keys.
        operation is called with (model_name, api_key).
        """
        model_index = 0

        while model_index < len(self.models):
            current_model = self.models[model_index]
            attempt = 0

            # Keep track of how many unique keys we've tried for this specific model run
            # to avoid spinning indefinitely if all keys are rate-limited simultaneously.
            tried_keys = set()

            while attempt < self.max_attempts:
                if not self.key_pool.has_keys():
                    raise ProviderError("All API keys exhausted across models")

                current_key = self.key_pool.get_next_key()
                tried_keys.add(current_key)

                try:
                    logger.debug(
                        f"Attempting {current_model} (attempt {attempt + 1}/{self.max_attempts})"
                    )
                    return await operation(current_model, current_key)

                except (ProviderQuotaError, ProviderRateLimitError) as e:
                    logger.warning(
                        f"Quota/Rate limit hit for {current_model}: {e}. Trying next key."
                    )

                    # If we've tried all currently available keys for this model loop,
                    # we should stop spinning and fall back to the next model.
                    available_keys = self.key_pool.get_all_keys()
                    if not available_keys or set(available_keys).issubset(tried_keys):
                        logger.warning(
                            f"All available keys tried on {current_model}. Moving to next model."
                        )
                        break

                    # Do not increment attempt for quota on a single key, just try next key on same model
                    # But we'll add a small delay to prevent tight loops when multiple coroutines hit rate limits
                    await self._sleep(0.1)
                    continue

                except ProviderTransientError as e:
                    attempt += 1
                    if attempt >= self.max_attempts:
                        logger.warning(
                            f"Max attempts reached for {current_model} due to transient error: {e}. Moving to next model."
                        )
                        break

                    delay = min(
                        self.max_delay, self.initial_delay * (2 ** (attempt - 1))
                    )
                    # Add jitter
                    actual_delay = delay + random.uniform(0, self.jitter * delay)
                    logger.info(f"Transient error. Retrying in {actual_delay:.2f}s...")
                    await self._sleep(actual_delay)

                except ProviderAuthenticationError as e:
                    logger.error(
                        f"Authentication error: {e}. Invalidating key globally."
                    )
                    self.key_pool.invalidate_key(current_key)
                    if not self.key_pool.has_keys():
                        break

                except ProviderInvalidRequestError as e:
                    logger.error(f"Invalid request: {e}. Failing immediately.")
                    raise

                except asyncio.CancelledError:
                    logger.info("Operation cancelled.")
                    raise

                except Exception as e:
                    logger.error(
                        f"Unknown provider error: {e}. Failing conservatively."
                    )
                    raise ProviderError(f"Unknown error during provider execution: {e}")

            model_index += 1
            if model_index < len(self.models):
                logger.info(f"Falling back to model {self.models[model_index]}")

            # If keys are permanently exhausted globally, we can't try any more models.
            if not self.key_pool.has_keys():
                raise ProviderError("All models and keys exhausted")

        raise ProviderError("All models and keys exhausted")
