"""Shared helpers for api-token v3 partner examples."""

import os
from typing import Iterable, Optional

from dotenv import load_dotenv

from limitless_sdk import (
    Client,
    ConsoleLogger,
    DeriveApiTokenInput,
    HMACCredentials,
    LogLevel,
)


load_dotenv()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value


def truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def ready_delay_ms() -> int:
    raw = os.getenv("LIMITLESS_DELEGATED_ACCOUNT_READY_DELAY_MS", "10000")
    try:
        return max(int(raw), 0)
    except ValueError:
        return 10000


def build_logger() -> ConsoleLogger:
    level = LogLevel.DEBUG if truthy_env("LIMITLESS_HTTP_TRACE") else LogLevel.INFO
    return ConsoleLogger(level=level)


def create_client(
    *,
    api_key: Optional[str] = None,
    hmac_credentials: Optional[HMACCredentials] = None,
) -> Client:
    return Client(
        base_url=os.getenv("LIMITLESS_API_URL"),
        api_key=api_key,
        hmac_credentials=hmac_credentials,
        logger=build_logger(),
    )


async def derive_scoped_client(
    identity_token: str,
    scopes: Iterable[str],
    label: str,
):
    bootstrap = create_client()
    derived = await bootstrap.api_tokens.derive_token(
        identity_token,
        DeriveApiTokenInput(label=label, scopes=list(scopes)),
    )
    scoped = create_client(
        hmac_credentials=HMACCredentials(
            token_id=derived.token_id,
            secret=derived.secret,
        )
    )
    return bootstrap, scoped, derived
