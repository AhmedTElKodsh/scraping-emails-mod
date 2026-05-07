import random
import time
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self,
        min_delay: float = 2.0,
        max_delay: float = 8.0,
        delay_fn: Callable[[], float] | None = None,
    ) -> None:
        self._min = min_delay
        self._max = max_delay
        self._delay_fn = delay_fn or (lambda: random.uniform(self._min, self._max))

    def wait(self) -> float:
        delay = self._delay_fn()
        time.sleep(delay)
        return delay
