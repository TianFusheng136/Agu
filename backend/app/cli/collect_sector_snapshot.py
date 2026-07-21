"""Collect one real-provider sector rotation snapshot without a running web server."""

import json
from typing import Protocol

from app.api.dependencies import get_market_radar_service
from app.services.market_radar import RotationSnapshotCollection


class SnapshotService(Protocol):
    def collect_rotation_snapshot(self) -> RotationSnapshotCollection: ...


def collect_snapshot(service: SnapshotService) -> tuple[int, dict[str, object]]:
    try:
        result = service.collect_rotation_snapshot()
    except Exception as error:
        return 1, {"state": "unavailable", "message": str(error)}
    return 0, result.model_dump(mode="json")


def main() -> int:
    exit_code, payload = collect_snapshot(get_market_radar_service())
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
