"""Receive-window helpers for order creation."""

import time
from typing import Callable, Dict, Optional


MAX_RECV_WINDOW_MS = 10_000


def _default_now_ms() -> int:
    return int(time.time() * 1000)


def normalize_receive_window_options(
    *,
    timestamp: Optional[int] = None,
    recv_window: Optional[int] = None,
    now_ms: Callable[[], int] = _default_now_ms,
) -> Dict[str, int]:
    """Validate and normalize optional POST /orders receive-window controls.

    The returned keys use Python model field names. Pydantic models serialize
    ``recv_window`` as the API's top-level ``recvWindow`` field.
    """
    if timestamp is not None and (
        isinstance(timestamp, bool)
        or not isinstance(timestamp, int)
        or timestamp < 0
    ):
        raise ValueError("timestamp must be a non-negative integer")

    if recv_window is not None:
        if isinstance(recv_window, bool) or not isinstance(recv_window, int):
            raise ValueError("recv_window must be an integer")
        if recv_window < 1 or recv_window > MAX_RECV_WINDOW_MS:
            raise ValueError(
                f"recv_window must be between 1 and {MAX_RECV_WINDOW_MS} milliseconds"
            )

    if timestamp is None and recv_window is None:
        return {}

    normalized: Dict[str, int] = {}
    if timestamp is not None:
        normalized["timestamp"] = timestamp
    if recv_window is not None:
        normalized["recv_window"] = recv_window
        normalized.setdefault("timestamp", now_ms())

    return normalized
