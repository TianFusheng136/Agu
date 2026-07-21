import asyncio

from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app


def test_health_endpoint() -> None:
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ai-market-radar",
    }


def test_app_lifespan_primes_the_market_service_before_requests(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        main_module,
        "get_market_radar_service",
        lambda: calls.append("initialized"),
        raising=False,
    )
    lifespan = getattr(main_module, "lifespan", None)

    assert lifespan is not None

    async def exercise_lifespan() -> None:
        async with lifespan(app):
            assert calls == ["initialized"]

    asyncio.run(exercise_lifespan())
