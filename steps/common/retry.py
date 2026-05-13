from __future__ import annotations
import random
import time
from typing import Callable, TypeVar, Tuple

import requests


T = TypeVar("T")


def request_with_retry(method: str, url: str, *, retries: int = 3, base_delay: float = 0.5, jitter: float = 0.2, allowed: Tuple[int, ...] = (200,), **kwargs) -> requests.Response:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.request(method, url, **kwargs)
            if r.status_code in allowed:
                return r
            last_err = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            last_err = e
        if attempt < retries - 1:
            delay = base_delay * (2 ** attempt) + random.uniform(0.0, jitter)
            time.sleep(delay)
    assert last_err is not None
    raise last_err

