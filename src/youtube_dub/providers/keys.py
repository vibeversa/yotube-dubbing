import logging

logger = logging.getLogger(__name__)


class ApiKeyPool:
    def __init__(self, keys: list[str]):
        if not keys:
            raise ValueError("ApiKeyPool requires at least one API key")
        self._keys = list(keys)
        self._current_index = 0
        self._exhausted = False

    @staticmethod
    def _mask_key(key: str) -> str:
        if len(key) <= 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"

    def get_current_key(self) -> str:
        if self._exhausted:
            raise ValueError("No valid API keys remaining in pool")
        return self._keys[self._current_index]

    def rotate(self) -> None:
        """Rotates to the next key. Marks pool as exhausted if we've tried all keys."""
        if self._exhausted:
            return

        old_key = self._keys[self._current_index]
        self._current_index += 1

        if self._current_index >= len(self._keys):
            self._exhausted = True
            self._current_index = 0  # keep pointing somewhere valid for safety
            logger.warning("All API keys in the pool have been exhausted.")
        else:
            new_key = self._keys[self._current_index]
            logger.info(
                f"Rotated API key from {self._mask_key(old_key)} to {self._mask_key(new_key)}"
            )

    def is_exhausted(self) -> bool:
        return self._exhausted
