from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
CODE_PATTERN = re.compile(r"^[A-Z0-9]{6,12}$")


def normalize_code(value: str) -> str:
    return re.sub(r"[\s\-]", "", value or "").upper()


def is_valid_code_shape(value: str) -> bool:
    return bool(CODE_PATTERN.match(value)) and len(value) == CODE_LENGTH


def generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def code_hmac(code: str, pepper: str) -> str:
    return hmac.new(
        pepper.encode("utf-8"), normalize_code(code).encode("utf-8"), hashlib.sha256
    ).hexdigest()


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def passwords_equal(candidate: str, expected: str) -> bool:
    if not expected:
        return False
    return hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))


class RateLimiter:
    """Small in-process limiter for login/code guessing.

    The application runs one API process, so in-memory state is sufficient for
    the MVP. Email login is a deliberately simple test gate; legacy code attempts
    remain bounded by high-entropy codes.
    """

    def __init__(self) -> None:
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(1, int(window_seconds - (now - bucket[0])))
            return False, retry_after
        bucket.append(now)
        return True, 0
