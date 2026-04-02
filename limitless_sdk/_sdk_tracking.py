"""Shared SDK tracking header helpers."""

import platform
from importlib.metadata import PackageNotFoundError, version
from typing import Dict


SDK_ID = "lmts-sdk-py"


def _resolve_sdk_version() -> str:
    try:
        return version("limitless-sdk")
    except PackageNotFoundError:
        return "0.0.0"


def _build_sdk_tracking_headers() -> Dict[str, str]:
    sdk_version = _resolve_sdk_version()
    return {
        "user-agent": f"{SDK_ID}/{sdk_version} (python/{platform.python_version()})",
        "x-sdk-version": f"{SDK_ID}/{sdk_version}",
    }
