"""Order lifecycle reconstruction."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Iterable

from .models import EventType, OrderEvent, OrderLifecycle, OrderStatus


def reconstruct_lifecycles(events: Iterable[OrderEvent]) -> dict[str, OrderLifecycle]:
    grouped: dict[str, list[OrderEvent]] = defaultdict(list)
    for event in events:
        if event.order_id:
            grouped[event.order_id].append(event)

    return {
        order_id: _build_lifecycle(order_id, sorted(order_events, key=_event_sort_key))
        for order_id, order_events in grouped.items()
    }


def _build_lifecycle(order_id: str, events: list[OrderEvent]) -> OrderLifecycle:
    new_events = _events_of_type(events, EventType.ORDER_NEW)
    ack_events = _events_of_type(events, EventType.ORDER_ACK)
    fill_events = _events_of_type(events, EventType.ORDER_FILL)
    reject_events = _events_of_type(events, EventType.ORDER_REJECT)
    cancel_events = _events_of_type(events, EventType.ORDER_CANCEL)

    first_new = new_events[0] if new_events else None
    first_ack = ack_events[0] if ack_events else None
    first_fill = fill_events[0] if fill_events else None
    first_reject = reject_events[0] if reject_events else None
    first_cancel = cancel_events[0] if cancel_events else None

    ordered_qty = first_new.qty if first_new else None
    filled_qty = sum(event.qty or 0 for event in fill_events)
    ack_latency_ms = _latency_ms(first_new.timestamp, first_ack.timestamp) if first_new and first_ack else None
    final_time = _last_timestamp(events)

    status = _determine_status(
        has_new=bool(first_new),
        has_ack=bool(first_ack),
        filled_qty=filled_qty,
        ordered_qty=ordered_qty,
        has_reject=bool(first_reject),
        has_cancel=bool(first_cancel),
        events=events,
    )

    return OrderLifecycle(
        order_id=order_id,
        events=events,
        status=status,
        symbol=_first_present(event.symbol for event in events),
        side=_first_present(event.side for event in events),
        ordered_qty=ordered_qty,
        filled_qty=filled_qty,
        new_time=first_new.timestamp if first_new else None,
        ack_time=first_ack.timestamp if first_ack else None,
        first_fill_time=first_fill.timestamp if first_fill else None,
        final_time=final_time,
        ack_latency_ms=ack_latency_ms,
        reject_reason=first_reject.reason if first_reject else None,
        cancel_reason=first_cancel.reason if first_cancel else None,
    )


def _determine_status(
    *,
    has_new: bool,
    has_ack: bool,
    filled_qty: int,
    ordered_qty: int | None,
    has_reject: bool,
    has_cancel: bool,
    events: list[OrderEvent],
) -> OrderStatus:
    if not has_new:
        known_events = [event for event in events if event.event_type is not EventType.UNKNOWN]
        return OrderStatus.INCOMPLETE if known_events else OrderStatus.UNKNOWN

    if has_reject:
        return OrderStatus.REJECTED
    if has_cancel:
        return OrderStatus.CANCELED
    if ordered_qty is not None and filled_qty >= ordered_qty and filled_qty > 0:
        return OrderStatus.FILLED
    if filled_qty > 0:
        return OrderStatus.PARTIALLY_FILLED
    if has_ack:
        return OrderStatus.ACKED
    return OrderStatus.NEW_ONLY


def _events_of_type(events: list[OrderEvent], event_type: EventType) -> list[OrderEvent]:
    return [event for event in events if event.event_type is event_type]


def _latency_ms(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return (end - start).total_seconds() * 1000


def _last_timestamp(events: list[OrderEvent]) -> datetime | None:
    timestamps = [event.timestamp for event in events if event.timestamp is not None]
    return max(timestamps) if timestamps else None


def _first_present(values: Iterable[str | None]) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _event_sort_key(event: OrderEvent) -> tuple[datetime, int]:
    return event.timestamp or datetime.min, event.line_number or 0
