"""Typed recovery metadata. No classification retries or changes a purchase key."""
from dataclasses import dataclass
from typing import Literal, Optional
from ..api.errors import APIError

PackErrorKind = Literal[
    "OTHER", "ALLOWANCE_REQUIRED", "NOT_SUBMITTED", "PRICE_DRIFTED",
    "INTENT_EXPIRED", "WALLET_BUSY", "RATE_LIMITED",
    "SUBMISSION_UNKNOWN", "TRANSACTION_REVERTED",
]


@dataclass(frozen=True)
class PackErrorDetails:
    kind: PackErrorKind = "OTHER"
    code: Optional[str] = None
    message: Optional[str] = None
    submission_state: Optional[str] = None
    parlay_id: Optional[str] = None
    recovery: Optional[str] = None
    token_address: Optional[str] = None
    spender: Optional[str] = None
    required_allowance: Optional[str] = None


def classify_pack_error(error: Exception) -> PackErrorDetails:
    if not isinstance(error, APIError):
        return PackErrorDetails()
    data = error.response_data if isinstance(error.response_data, dict) else {}

    def string(key):
        value = data.get(key)
        return value if isinstance(value, str) else None

    code, state, status = string("code"), string("submissionState"), error.status_code
    kind: PackErrorKind = "OTHER"
    if status == 409 and code == "PACK_SUBMISSION_UNKNOWN":
        kind = "SUBMISSION_UNKNOWN"
    elif status is not None and 400 <= status < 500 and status != 429 and state == "NOT_SUBMITTED":
        kind = "NOT_SUBMITTED"
    elif status == 409 and code == "PACK_ALLOWANCE_REQUIRED":
        kind = "ALLOWANCE_REQUIRED"
    elif status == 409 and code == "PRICE_DRIFTED":
        kind = "PRICE_DRIFTED"
    elif status == 401 and error.message == "Intent expired — please retry":
        kind = "INTENT_EXPIRED"
    elif status == 409 and error.message == "Another Pack operation is in progress for this wallet; retry the same request":
        kind = "WALLET_BUSY"
    elif status == 429:
        kind = "RATE_LIMITED"
    elif status == 409 and code == "PACK_TRANSACTION_REVERTED":
        kind = "TRANSACTION_REVERTED"
    return PackErrorDetails(
        kind=kind, code=code, message=error.message, submission_state=state,
        parlay_id=string("parlayId"), recovery=string("recovery"),
        token_address=string("tokenAddress"), spender=string("spender"),
        required_allowance=string("requiredAllowance"),
    )
