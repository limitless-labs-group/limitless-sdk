"""HMAC helpers for scoped API-token authentication."""

import base64
import hashlib
import hmac


def compute_hmac_signature(
    secret: str,
    timestamp: str,
    method: str,
    path: str,
    body: str,
) -> str:
    """Compute the Limitless HMAC signature for a request."""
    decoded_secret = base64.b64decode(secret)
    message = f"{timestamp}\n{method.upper()}\n{path}\n{body}"
    digest = hmac.new(decoded_secret, message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")
