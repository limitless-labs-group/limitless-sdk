"""OME order event TypedDicts must match the gateway wire shapes."""

from typing import Union, get_args, get_type_hints

from limitless_sdk.websocket import (
    OmeExecutionOrderEvent,
    OmeLifecycleOrderEvent,
    OmeOrderEvent,
)

# Zero-fill FAK as observed on production, 2026-09-25.
KILLED: OmeExecutionOrderEvent = {
    "source": "OME",
    "type": "EXECUTION",
    "status": "KILLED",
    "eventId": "terminal:821277de-1b92-4b37-bba3-34ff3d26a79e",
    "orderId": "821277de-1b92-4b37-bba3-34ff3d26a79e",
    "userId": 42,
    "marketId": "409786",
    "token": "73663029485913087603",
    "side": "BUY",
    "price": "0.01",
    "remainingSize": "50000000",
    "timestamp": "2026-09-25T13:55:55.098321+00:00",
    "occurredAt": "2026-09-25T13:55:55.100Z",
    "publishedAt": "2026-09-25T13:55:55.106Z",
}


def remaining_shares(event: OmeOrderEvent) -> float:
    if event["type"] == "EXECUTION":
        return float(event["remainingSize"]) / 1_000_000
    return event["remainingSize"] / 1_000_000


def test_execution_frame_fields_are_strings() -> None:
    hints = get_type_hints(OmeExecutionOrderEvent)
    assert hints["price"] is str
    assert hints["remainingSize"] is str
    assert hints["eventId"] is str


def test_lifecycle_frame_fields_are_numbers() -> None:
    hints = get_type_hints(OmeLifecycleOrderEvent)
    assert hints["price"] is float
    assert hints["remainingSize"] is float
    assert hints["eventId"] is int


def test_ome_order_event_is_the_union_of_both_shapes() -> None:
    assert set(get_args(OmeOrderEvent)) == {OmeLifecycleOrderEvent, OmeExecutionOrderEvent}
    assert Union[OmeLifecycleOrderEvent, OmeExecutionOrderEvent] == OmeOrderEvent


def test_narrowing_on_type_recovers_shares() -> None:
    assert remaining_shares(KILLED) == 50.0
