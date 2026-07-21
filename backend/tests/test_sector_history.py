import json
from datetime import datetime

from app.domain.sector_taxonomy import classify_sector, industry_sector_id
from app.providers.demo import DemoMarketDataProvider
from app.services.market_radar import MarketRadarService
from app.services.sector_history import (
    FileSectorSnapshotStore,
    InMemorySectorSnapshotStore,
)


def test_audited_sector_aliases_share_one_stable_industry_id() -> None:
    assert classify_sector(
        "煤炭", has_cross_source_mapping=False
    ).canonical_name == "煤炭开采加工"
    assert industry_sector_id("煤炭") == industry_sector_id("煤炭开采加工")
    assert industry_sector_id("石油") == industry_sector_id("油气开采及服务")


def test_file_store_migrates_legacy_alias_ids_without_splitting_history(
    tmp_path,
) -> None:
    path = tmp_path / "sector-snapshots.json"
    classification = classify_sector("煤炭", has_cross_source_mapping=False)
    common = {
        "as_of": "2026-07-20T15:00:00+08:00",
        "rank": 2,
        "heat_score": 70.0,
        "capital_flow_billion": 10.0,
        "classification": classification.model_dump(mode="json"),
    }
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "points": [
                    {
                        **common,
                        "sector_id": "industry-煤炭开采加工",
                        "sector_name": "煤炭开采加工",
                        "change_pct": 2.0,
                    },
                    {
                        **common,
                        "sector_id": "industry-煤炭",
                        "sector_name": "煤炭",
                        "change_pct": 1.0,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    store = FileSectorSnapshotStore(path)
    points = store.list_sector("industry-煤炭开采加工", days=20)

    assert len(points) == 1
    assert points[0].sector_id == "industry-煤炭开采加工"
    assert points[0].sector_name == "煤炭开采加工"
    assert points[0].change_pct == 2.0


def test_sector_rotation_is_explicitly_collecting_before_enough_daily_snapshots() -> None:
    service = MarketRadarService(
        DemoMarketDataProvider(),
        history_store=InMemorySectorSnapshotStore(),
    )

    rotation = service.get_sector_rotation("ai-server", days=20)

    assert rotation.status == "collecting"
    assert rotation.minimum_required_points == 5
    assert rotation.data_points == 1
    assert rotation.points[0].sector_id == "ai-server"
    assert rotation.classification.canonical_name == "AI服务器"
    assert rotation.capital_flow_label == "行业资金净额（非主力净流入）"


def test_snapshot_store_keeps_the_newest_snapshot_for_each_trading_date() -> None:
    store = InMemorySectorSnapshotStore()
    service = MarketRadarService(DemoMarketDataProvider(), history_store=store)
    overview = service.get_overview()
    first_sector = overview.hot_sectors[0]

    store.record_sector(
        sector=first_sector,
        as_of=datetime.fromisoformat("2026-07-17T10:00:00+08:00"),
        rank=1,
    )
    store.record_sector(
        sector=first_sector.model_copy(update={"change_pct": 9.99}),
        as_of=datetime.fromisoformat("2026-07-17T14:50:00+08:00"),
        rank=1,
    )

    points = store.list_sector(first_sector.id, days=20)

    assert len(points) == 1
    assert points[0].as_of == "2026-07-17T14:50:00+08:00"
    assert points[0].change_pct == 9.99


def test_sector_detail_uses_the_last_seen_snapshot_when_upstream_rotates_between_requests() -> None:
    payload = DemoMarketDataProvider().get_market_payload()

    class RotatingProvider:
        def __init__(self) -> None:
            self.calls = 0

        def get_market_payload(self):
            self.calls += 1
            if self.calls == 1:
                return payload
            return payload.model_copy(update={"sectors": []})

    service = MarketRadarService(RotatingProvider())
    first_sector = service.get_overview().hot_sectors[0]

    detail = service.get_sector_detail(first_sector.id)

    assert detail is not None
    assert detail.id == first_sector.id
