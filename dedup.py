import time
import logging

logger = logging.getLogger(__name__)


class DeduplicationCache:
    """In-memory TTL cache to handle Chatwoot's double-fire webhook bug."""

    def __init__(self, ttl_seconds=10):
        self._cache = {}  # key -> expiry timestamp
        self.ttl = ttl_seconds

    def is_duplicate(self, key):
        """Check if key was seen within TTL. If not, record it and return False."""
        self._cleanup()
        now = time.time()

        if key in self._cache:
            logger.debug("Dedup hit: %s", key)
            return True

        self._cache[key] = now + self.ttl
        return False

    def _cleanup(self):
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, expiry in self._cache.items() if expiry <= now]
        for k in expired:
            del self._cache[k]
