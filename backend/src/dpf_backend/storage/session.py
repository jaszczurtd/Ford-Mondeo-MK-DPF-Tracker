"""Boot/session detection for tracker records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from dpf_backend.ingest.models import ParsedMessage


LONG_GAP_THRESHOLD = timedelta(minutes=30)
SMALL_UPTIME_MS = 5 * 60 * 1000


@dataclass(frozen=True)
class SessionObservation:
    device_id: str
    received_at: datetime
    device_ms: int | None
    min_event_seq: int | None
    max_event_seq: int | None
    watchdog_reset: bool


@dataclass(frozen=True)
class CurrentSession:
    id: int
    device_id: str
    started_at: datetime
    updated_at: datetime
    last_device_ms: int | None
    last_event_seq: int | None


@dataclass(frozen=True)
class SessionDecision:
    start_new: bool
    reason: str


def observation_from_message(message: ParsedMessage) -> SessionObservation:
    device_ms = None
    min_event_seq = None
    max_event_seq = None
    watchdog_reset = False

    if message.telemetry is not None:
        device_ms = _int_or_none(message.telemetry.payload.get("ms"))

    if message.status is not None:
        device_ms = _int_or_none(message.status.payload.get("ms"))
        watchdog_reset = bool(message.status.payload.get("watchdog_reset"))

    seq_values = [
        seq
        for seq in (
            _int_or_none(event.event_payload.get("seq"))
            for event in message.actuator_events
        )
        if seq is not None
    ]
    if seq_values:
        min_event_seq = min(seq_values)
        max_event_seq = max(seq_values)
    if message.actuator_events:
        device_ms = _int_or_none(message.actuator_events[0].batch_payload.get("ms"))

    return SessionObservation(
        device_id=message.raw.device_id,
        received_at=message.raw.received_at,
        device_ms=device_ms,
        min_event_seq=min_event_seq,
        max_event_seq=max_event_seq,
        watchdog_reset=watchdog_reset,
    )


def decide_session(
    current: CurrentSession | None,
    observation: SessionObservation,
) -> SessionDecision:
    if current is None:
        return SessionDecision(True, "watchdog_reset" if observation.watchdog_reset else "initial")

    if observation.watchdog_reset:
        return SessionDecision(True, "watchdog_reset")

    if (
        observation.device_ms is not None
        and current.last_device_ms is not None
        and observation.device_ms < current.last_device_ms
    ):
        return SessionDecision(True, "device_ms_reset")

    if (
        observation.min_event_seq is not None
        and current.last_event_seq is not None
        and observation.min_event_seq < current.last_event_seq
    ):
        return SessionDecision(True, "event_seq_reset")

    gap = observation.received_at - current.updated_at
    if (
        observation.device_ms is not None
        and gap > LONG_GAP_THRESHOLD
        and observation.device_ms < SMALL_UPTIME_MS
    ):
        return SessionDecision(True, "long_gap_small_uptime")

    return SessionDecision(False, "same_session")


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

