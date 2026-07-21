from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_market_radar_service
from app.domain.contracts import FrozenModel
from app.services.market_radar import MarketRadarService

router = APIRouter(tags=["search"])


class SearchResult(FrozenModel):
    kind: Literal["sector", "stock", "etf"]
    id: str
    name: str
    subtitle: str


@router.get("/search", response_model=list[SearchResult])
def search_market(
    q: Annotated[str, Query(min_length=1, max_length=40)],
    service: Annotated[MarketRadarService, Depends(get_market_radar_service)],
) -> list[SearchResult]:
    normalized = q.strip().casefold()
    if not normalized:
        raise HTTPException(status_code=422, detail="搜索词不能为空")

    results: list[SearchResult] = []
    seen: set[tuple[str, str]] = set()

    def add(result: SearchResult) -> None:
        key = (result.kind, result.id)
        if key not in seen:
            seen.add(key)
            results.append(result)

    if len(normalized) == 6 and normalized.isdigit():
        for stock in service.search_stocks(normalized, limit=12):
            if stock.code == normalized:
                return [
                    SearchResult(
                        kind="stock",
                        id=stock.code,
                        name=stock.name,
                        subtitle=f"{stock.code} · A股",
                    )
                ]

    overview = service.get_overview()
    for sector in overview.hot_sectors:
        if normalized in f"{sector.name} {sector.core_direction}".casefold():
            add(
                SearchResult(
                    kind="sector",
                    id=sector.id,
                    name=sector.name,
                    subtitle=f"{sector.core_direction} · 热度 {sector.heat.score:.1f}",
                )
            )
        for stock in sector.stocks:
            if normalized in f"{stock.code} {stock.name} {stock.direction}".casefold():
                add(
                    SearchResult(
                        kind="stock",
                        id=stock.code,
                        name=stock.name,
                        subtitle=f"{stock.code} · {stock.direction} · {sector.name}",
                    )
                )
        for etf in sector.etfs:
            if normalized in f"{etf.code} {etf.name} {etf.coverage_direction}".casefold():
                add(
                    SearchResult(
                        kind="etf",
                        id=etf.code,
                        name=etf.name,
                        subtitle=f"{etf.code} · {etf.coverage_direction}",
                    )
                )

    if not results:
        for stock in service.search_stocks(normalized, limit=12):
            add(
                SearchResult(
                    kind="stock",
                    id=stock.code,
                    name=stock.name,
                    subtitle=f"{stock.code} · A股",
                )
            )

    exact_matches = [
        item
        for item in results
        if normalized in {item.id.casefold(), item.name.casefold()}
    ]
    partial_matches = [item for item in results if item not in exact_matches]
    return (exact_matches + partial_matches)[:12]
