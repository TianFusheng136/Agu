from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.dependencies import get_market_radar_service
from app.api.router import api_router
from app.providers.base import MarketDataUnavailable


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    del application
    get_market_radar_service()
    yield


app = FastAPI(
    title="AI短线市场雷达",
    description="面向中国A股的市场研究辅助工具",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.exception_handler(MarketDataUnavailable)
def market_data_unavailable_handler(
    request: Request, error: MarketDataUnavailable
) -> JSONResponse:
    del request
    return JSONResponse(status_code=503, content={"detail": str(error)})
