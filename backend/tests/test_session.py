from datetime import datetime, timedelta, timezone

from dpf_backend.storage.session import (
    CurrentSession,
    SessionObservation,
    decide_session,
)


NOW = datetime(2026, 6, 20, 0, 0, tzinfo=timezone.utc)


def current_session(
    *,
    last_device_ms: int | None = 100_000,
    last_event_seq: int | None = 10,
    updated_at: datetime = NOW,
) -> CurrentSession:
    return CurrentSession(
        id=1,
        device_id="dpf-tracker",
        started_at=NOW - timedelta(minutes=10),
        updated_at=updated_at,
        last_device_ms=last_device_ms,
        last_event_seq=last_event_seq,
    )


def observation(
    *,
    device_ms: int | None = 110_000,
    min_event_seq: int | None = 11,
    max_event_seq: int | None = 12,
    watchdog_reset: bool = False,
    received_at: datetime = NOW + timedelta(seconds=1),
) -> SessionObservation:
    return SessionObservation(
        device_id="dpf-tracker",
        received_at=received_at,
        device_ms=device_ms,
        min_event_seq=min_event_seq,
        max_event_seq=max_event_seq,
        watchdog_reset=watchdog_reset,
    )


def test_first_observation_starts_initial_session() -> None:
    decision = decide_session(None, observation())
    assert decision.start_new is True
    assert decision.reason == "initial"


def test_watchdog_observation_starts_new_session() -> None:
    decision = decide_session(current_session(), observation(watchdog_reset=True))
    assert decision.start_new is True
    assert decision.reason == "watchdog_reset"


def test_device_ms_drop_starts_new_session() -> None:
    decision = decide_session(current_session(last_device_ms=100_000), observation(device_ms=10))
    assert decision.start_new is True
    assert decision.reason == "device_ms_reset"


def test_event_seq_drop_starts_new_session() -> None:
    decision = decide_session(
        current_session(last_event_seq=100),
        observation(min_event_seq=2, max_event_seq=3),
    )
    assert decision.start_new is True
    assert decision.reason == "event_seq_reset"


def test_long_gap_with_small_uptime_starts_new_session() -> None:
    decision = decide_session(
        current_session(updated_at=NOW - timedelta(hours=1), last_device_ms=None),
        observation(device_ms=10_000, min_event_seq=None, max_event_seq=None),
    )
    assert decision.start_new is True
    assert decision.reason == "long_gap_small_uptime"


def test_normal_progress_keeps_same_session() -> None:
    decision = decide_session(current_session(), observation())
    assert decision.start_new is False
    assert decision.reason == "same_session"
