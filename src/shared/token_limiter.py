"""In-memory global token limiter for Block 0."""
import threading
import time
from dataclasses import dataclass


@dataclass
class TokenLimiter:
    tokens_per_minute: int = 8000
    window_seconds: float = 60.0

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._used = 0
        self._window_start = time.monotonic()

    def acquire(self, tokens: int) -> float:
        with self._lock:
            now = time.monotonic()
            if now - self._window_start >= self.window_seconds:
                self._used = 0
                self._window_start = now
            if self._used + tokens > self.tokens_per_minute:
                wait = self.window_seconds - (now - self._window_start)
                return max(wait, 0.0)
            self._used += tokens
            return 0.0