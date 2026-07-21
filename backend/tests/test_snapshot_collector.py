from app.cli.collect_sector_snapshot import collect_snapshot
from app.services.market_radar import RotationSnapshotCollection


def test_cli_collector_returns_only_the_service_snapshot_result() -> None:
    class SnapshotService:
        def collect_rotation_snapshot(self) -> RotationSnapshotCollection:
            return RotationSnapshotCollection(
                state="recorded",
                as_of="2026-07-20T15:10:00+08:00",
                sectors_recorded=3,
                message="recorded from provider",
            )

    exit_code, payload = collect_snapshot(SnapshotService())

    assert exit_code == 0
    assert payload["state"] == "recorded"
    assert payload["sectors_recorded"] == 3


def test_cli_collector_reports_a_provider_failure_without_a_fallback() -> None:
    class UnavailableService:
        def collect_rotation_snapshot(self) -> RotationSnapshotCollection:
            raise RuntimeError("upstream unavailable")

    exit_code, payload = collect_snapshot(UnavailableService())

    assert exit_code == 1
    assert payload == {"state": "unavailable", "message": "upstream unavailable"}
