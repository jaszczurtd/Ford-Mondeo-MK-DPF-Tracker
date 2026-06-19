from pathlib import Path


def test_initial_migration_defines_required_tables() -> None:
    sql = Path("backend/db/migrations/001_initial_schema.sql").read_text(
        encoding="utf-8"
    )
    for table in (
        "schema_migrations",
        "raw_mqtt",
        "boot_sessions",
        "telemetry_data",
        "actuator_events",
        "status_events",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql


def test_initial_migration_records_itself() -> None:
    sql = Path("backend/db/migrations/001_initial_schema.sql").read_text(
        encoding="utf-8"
    )
    assert "INSERT INTO schema_migrations" in sql
    assert "001_initial_schema" in sql
