import asyncio
import logging
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

            while attempt < self.max_attempts:
                if self.key_pool.is_exhausted():
                    raise ProviderError("All API keys exhausted across models")

                current_key = self.key_pool.get_current_key()

                try:
                    logger.debug(
                        f"Attempting {current_model} (attempt {attempt + 1}/{self.max_attempts})"
                    )
                    return await operation(current_model, current_key)

                except (ProviderQuotaError, ProviderRateLimitError) as e:
                    logger.warning(
                        f"Quota/Rate limit hit for {current_model}: {e}. Rotating key."
                    )
                    self.key_pool.rotate()
                    if self.key_pool.is_exhausted():
                        logger.warning(
                            f"Key pool exhausted on {current_model}. Moving to next model."
                        )
                        break  # Break out to next model if keys exhausted
                    # Do not increment attempt for quota on a single key, just try next key on same model

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
                    # add jitter here if needed
                    logger.info(f"Transient error. Retrying in {delay}s...")
                    await self._sleep(delay)

                except ProviderAuthenticationError as e:
                    logger.error(f"Authentication error: {e}. Rotating key.")
                    self.key_pool.rotate()
                    if self.key_pool.is_exhausted():
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

            # If keys are exhausted, we can't try any more models.
            if self.key_pool.is_exhausted():
                raise ProviderError("All models and keys exhausted")

        raise ProviderError("All models and keys exhausted")
