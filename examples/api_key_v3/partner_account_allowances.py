"""Partner server-wallet allowance check and retry example.

This example uses only partner HMAC auth:
- GET /profiles/partner-accounts/:profileId/allowances
- POST /profiles/partner-accounts/:profileId/allowances/retry
"""

import asyncio
import os
from typing import Any, List, Optional

from limitless_sdk import (
    ConflictError,
    HMACCredentials,
    PartnerAccountAllowanceResponse,
    PartnerAccountAllowanceStatusFailed,
    PartnerAccountAllowanceStatusMissing,
    PartnerAccountAllowanceStatusSubmitted,
    PartnerAccountAllowanceTarget,
    RateLimitError,
)

from common import create_client, require_env, truthy_env


def _positive_int_env(name: str) -> Optional[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def partner_account_profile_id() -> int:
    profile_id = _positive_int_env("LIMITLESS_PARTNER_ACCOUNT_PROFILE_ID")
    if profile_id is not None:
        return profile_id

    on_behalf_of = _positive_int_env("LIMITLESS_ON_BEHALF_OF")
    if on_behalf_of is not None:
        return on_behalf_of

    raise ValueError("LIMITLESS_PARTNER_ACCOUNT_PROFILE_ID is required")


def has_retryable_missing_or_failed_target(
    targets: List[PartnerAccountAllowanceTarget],
) -> bool:
    return any(
        target.retryable
        and target.status
        in {
            PartnerAccountAllowanceStatusMissing,
            PartnerAccountAllowanceStatusFailed,
        }
        for target in targets
    )


def submitted_targets(targets: List[PartnerAccountAllowanceTarget]) -> int:
    return sum(
        1
        for target in targets
        if target.status == PartnerAccountAllowanceStatusSubmitted
    )


def retry_after_seconds(response_data: Any) -> str:
    if isinstance(response_data, dict):
        value = response_data.get("retryAfterSeconds")
        if isinstance(value, int):
            return str(value)
    return "(not provided)"


def handle_retry_error(error: Exception) -> None:
    if isinstance(error, RateLimitError):
        print(
            "Retry is rate limited. "
            f"retryAfterSeconds={retry_after_seconds(error.response_data)}"
        )
    elif isinstance(error, ConflictError):
        print(
            "Another allowance retry is already running. "
            "Wait briefly and poll the GET endpoint again."
        )
    raise error


def print_allowance_response(response: PartnerAccountAllowanceResponse) -> None:
    print(
        f"profile_id={response.profile_id} "
        f"partner_profile_id={response.partner_profile_id} "
        f"chain_id={response.chain_id} "
        f"wallet={response.wallet_address} "
        f"ready={response.ready}"
    )
    print(
        "summary: "
        f"total={response.summary.total} "
        f"confirmed={response.summary.confirmed} "
        f"missing={response.summary.missing} "
        f"submitted={response.summary.submitted} "
        f"failed={response.summary.failed}"
    )

    for index, target in enumerate(response.targets):
        details = [
            f"target[{index}]: type={target.type}",
            f"label={target.label}",
            f"required_for={target.required_for}",
            f"status={target.status}",
            f"confirmed={target.confirmed}",
            f"retryable={target.retryable}",
            f"spender_or_operator={target.spender_or_operator}",
        ]
        if target.transaction_id:
            details.append(f"transaction_id={target.transaction_id}")
        if target.tx_hash:
            details.append(f"tx_hash={target.tx_hash}")
        if target.user_operation_hash:
            details.append(f"user_operation_hash={target.user_operation_hash}")
        if target.error_code:
            details.append(f"error_code={target.error_code}")
        if target.error_message:
            details.append(f"error_message={target.error_message!r}")
        print(" ".join(details))


async def main() -> None:
    profile_id = partner_account_profile_id()
    skip_retry = truthy_env("LIMITLESS_SKIP_ALLOWANCE_RETRY")
    client = create_client(
        hmac_credentials=HMACCredentials(
            token_id=require_env("LIMITLESS_API_TOKEN_ID"),
            secret=require_env("LIMITLESS_API_TOKEN_SECRET"),
        )
    )

    try:
        print(f"GET /profiles/partner-accounts/{profile_id}/allowances")
        allowances = await client.partner_accounts.check_allowances(profile_id)
        print_allowance_response(allowances)

        if allowances.ready:
            print("Allowance targets are ready.")
            return
        if not has_retryable_missing_or_failed_target(allowances.targets):
            print("No retryable missing or failed targets were returned.")
            return
        if skip_retry:
            print("Skipping retry because LIMITLESS_SKIP_ALLOWANCE_RETRY is enabled.")
            return

        print(f"POST /profiles/partner-accounts/{profile_id}/allowances/retry")
        try:
            retried = await client.partner_accounts.retry_allowances(profile_id)
        except Exception as exc:
            handle_retry_error(exc)

        print_allowance_response(retried)
        if submitted_targets(retried.targets) > 0:
            print(
                "Retry submitted sponsored allowance work. "
                "Poll the GET endpoint again after a short delay."
            )
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
