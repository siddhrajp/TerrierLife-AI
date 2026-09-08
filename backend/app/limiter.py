"""Shared rate limiter.

Must be a single instance: slowapi enforces limits against the limiter that
decorated the route, while the app registers one in `app.state` for its error
handler. Two separate instances means configuration applied to one silently
doesn't govern the other.

Storage defaults to in-process memory, which resets on restart and is per
-process — so N workers or N instances each allow the full quota. Set REDIS_URL
in any multi-instance deployment for limits to actually hold.
"""
import logging
import os

from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

_storage_uri = os.getenv("REDIS_URL")
if not _storage_uri:
    logger.warning(
        "rate_limiter_using_memory_storage: limits are per-process and reset on "
        "restart. Set REDIS_URL for shared, durable limits."
    )

DEFAULT_QUERY_LIMIT = os.getenv("QUERY_RATE_LIMIT", "10/day")

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage_uri,          # None -> in-memory
    default_limits=[],
)
