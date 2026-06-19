from dpf_backend.analyzer.windows import REFRESH_WINDOWS_SQL, WINDOW_BUCKET_SECONDS


def test_supported_window_buckets() -> None:
    assert WINDOW_BUCKET_SECONDS == (10, 60)


def test_refresh_windows_sql_placeholder_count() -> None:
    assert REFRESH_WINDOWS_SQL.count("%s") == 8


def test_refresh_windows_sql_targets_expected_table() -> None:
    assert "INSERT INTO telemetry_windows" in REFRESH_WINDOWS_SQL
    assert "FROM telemetry_data" in REFRESH_WINDOWS_SQL
    assert "FROM actuator_events" in REFRESH_WINDOWS_SQL
