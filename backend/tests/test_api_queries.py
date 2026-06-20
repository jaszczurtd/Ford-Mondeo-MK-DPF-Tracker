from dpf_backend.api import queries


def test_clamp_limit_defaults_and_bounds() -> None:
    assert queries.clamp_limit(None) == queries.DEFAULT_LIMIT
    assert queries.clamp_limit(0) == 1
    assert queries.clamp_limit(-5) == 1
    assert queries.clamp_limit(42) == 42
    assert queries.clamp_limit(queries.MAX_LIMIT + 1) == queries.MAX_LIMIT


def test_api_queries_reference_expected_tables() -> None:
    source = queries.ApiStore.backend_status.__code__.co_consts
    joined = "\n".join(str(item) for item in source)
    assert "raw_mqtt" in joined
    assert "telemetry_data" in joined
    assert "actuator_events" in joined
    assert "status_events" in joined
    assert "boot_sessions" in joined


def test_where_sql_builds_expected_clause() -> None:
    assert queries._where_sql([]) == ""
    assert queries._where_sql(["topic = %s", "device_id = %s"]) == (
        " WHERE topic = %s AND device_id = %s"
    )
