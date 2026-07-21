"""Small, transparent local store for daily sector-rotation snapshots.

This is deliberately a local JSON store for the MVP. It records only facts
returned by the live provider and never synthesizes history for a live source.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Literal, Protocol

from app.domain.contracts import FrozenModel
from app.domain.sector_taxonomy import (
    SectorClassification,
    canonical_sector_name,
    industry_sector_id,
)

if TYPE_CHECKING:
    from app.services.market_radar import SectorOverview


class SectorRotationPoint(FrozenModel):
    sector_id: str
    sector_name: str
    as_of: str
    rank: int | None = None
    heat_score: float | None = None
    change_pct: float
    capital_flow_billion: float | None
    classification: SectorClassification
    basis: Literal["source-price-history", "live-snapshot"] = "live-snapshot"
    strength_score: float | None = None
    relative_strength_pct: float | None = None
    turnover_change_pct: float | None = None
    volume_change_pct: float | None = None


class SectorSnapshotStore(Protocol):
    def record_sector(
        self,
        *,
        sector: "SectorOverview",
        as_of: datetime,
        rank: int,
    ) -> None: ...

    def list_sector(self, sector_id: str, days: int) -> list[SectorRotationPoint]: ...


class InMemorySectorSnapshotStore:
    def __init__(self) -> None:
        self._points: dict[tuple[str, str], SectorRotationPoint] = {}

    def record_sector(
        self,
        *,
        sector: "SectorOverview",
        as_of: datetime,
        rank: int,
    ) -> None:
        point, _ = _normalize_industry_point(
            _point_from_sector(sector=sector, as_of=as_of, rank=rank)
        )
        self._points[(point.sector_id, _trading_date(point.as_of))] = point

    def list_sector(self, sector_id: str, days: int) -> list[SectorRotationPoint]:
        stable_id = _stable_industry_id(sector_id)
        points = [point for point in self._points.values() if point.sector_id == stable_id]
        return sorted(points, key=lambda point: point.as_of)[-days:]


class FileSectorSnapshotStore(InMemorySectorSnapshotStore):
    def __init__(self, path: Path, retention_days: int = 180) -> None:
        super().__init__()
        self._path = path
        self._retention_days = retention_days
        self._lock = Lock()
        self._load()

    def record_sector(
        self,
        *,
        sector: "SectorOverview",
        as_of: datetime,
        rank: int,
    ) -> None:
        with self._lock:
            super().record_sector(sector=sector, as_of=as_of, rank=rank)
            self._trim()
            self._save()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            preferred_keys: set[tuple[str, str]] = set()
            for raw in payload.get("points", []):
                point, is_preferred = _normalize_industry_point(
                    SectorRotationPoint.model_validate(raw)
                )
                key = (point.sector_id, _trading_date(point.as_of))
                if key not in self._points or is_preferred or key not in preferred_keys:
                    self._points[key] = point
                if is_preferred:
                    preferred_keys.add(key)
        except (OSError, ValueError, json.JSONDecodeError):
            # A damaged local cache must never break public market data delivery.
            self._points = {}

    def _trim(self) -> None:
        dates = sorted({_trading_date(point.as_of) for point in self._points.values()})
        keep = set(dates[-self._retention_days :])
        self._points = {
            key: point
            for key, point in self._points.items()
            if _trading_date(point.as_of) in keep
        }

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "points": [
                point.model_dump(mode="json")
                for point in sorted(
                    self._points.values(), key=lambda item: (item.as_of, item.sector_id)
                )
            ],
        }
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temporary, self._path)


def _trading_date(as_of: str) -> str:
    return as_of[:10]


def _stable_industry_id(sector_id: str) -> str:
    if not sector_id.startswith("industry-"):
        return sector_id
    return industry_sector_id(sector_id.removeprefix("industry-"))


def _normalize_industry_point(
    point: SectorRotationPoint,
) -> tuple[SectorRotationPoint, bool]:
    if not point.sector_id.startswith("industry-"):
        return point, True
    canonical_name = canonical_sector_name(point.sector_name)
    stable_id = industry_sector_id(canonical_name)
    is_preferred = (
        point.sector_name.strip() == canonical_name and point.sector_id == stable_id
    )
    classification = point.classification.model_copy(
        update={"canonical_name": canonical_name}
    )
    return (
        point.model_copy(
            update={
                "sector_id": stable_id,
                "sector_name": canonical_name,
                "classification": classification,
            }
        ),
        is_preferred,
    )


def _point_from_sector(
    *,
    sector: "SectorOverview",
    as_of: datetime,
    rank: int,
) -> SectorRotationPoint:
    return SectorRotationPoint(
        sector_id=sector.id,
        sector_name=sector.name,
        as_of=as_of.isoformat(),
        rank=rank,
        heat_score=sector.heat.score,
        change_pct=sector.change_pct,
        capital_flow_billion=sector.capital_flow_billion,
        classification=sector.classification,
    )
