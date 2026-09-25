import logging
import threading

logger = logging.getLogger(__name__)


class ApiKeyPool:
    def __init__(self, keys: list[str]):
        if not keys:
            raise ValueError("ApiKeyPool requires at least one API key")
        self._keys = list(keys)
        self._lock = threading.Lock()
        self._current_index = 0

    @staticmethod
    def _mask_key(key: str) -> str:
        if len(key) <= 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"

    def get_next_key(self) -> str:
        """Gets the next key in a round-robin fashion."""
        with self._lock:
            if not self._keys:
                raise ValueError("No valid API keys remaining in pool")
            key = self._keys[self._current_index]
            self._current_index = (self._current_index + 1) % len(self._keys)
            return key

    def invalidate_key(self, key: str) -> None:
        """Permanently removes a key from the pool (e.g., due to auth error)."""
        with self._lock:
            if key in self._keys:
                idx = self._keys.index(key)
                self._keys.pop(idx)
                if self._keys:
                    if self._current_index >= len(self._keys):
                        self._current_index = 0
                    elif self._current_index > idx:
                        self._current_index -= 1
                else:
                    self._current_index = 0
                logger.warning(
                    f"Invalidated and removed API key {self._mask_key(key)}. Remaining keys: {len(self._keys)}"
                )

    def get_all_keys(self) -> list[str]:
        """Returns a snapshot of currently valid keys."""
        with self._lock:
            return list(self._keys)

    def has_keys(self) -> bool:
        with self._lock:
            return len(self._keys) > 0
