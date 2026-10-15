from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import ai_council, dashboard, execution, portfolio, research, risk
from .websocket import market_stream


def _create_initial_state():
    from orion.dashboard.web import DashboardState

    state = DashboardState()
    try:
        prices = [100.0 + i * 0.25 for i in range(40)]
        state.run_cycle("NVDA", prices)
        state.run_cycle("AAPL", [220.0 + i * 0.2 for i in range(40)])
        state.run_cycle("TSLA", [230.0 + i * 0.3 for i in range(40)])
    except Exception as e:
        print(f"Notice: Simulated trade seeding completed with note: {e}")
    return state


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    if not hasattr(app.state, "orion") or app.state.orion is None:
        app.state.orion = _create_initial_state()
    yield


app = FastAPI(
    title="Orion API Gateway",
    version="0.1.0",
    description="Backend For Frontend (BFF) connecting the Next.js UI to the Orion research engine.",
    lifespan=lifespan,
)
app.state.orion = _create_initial_state()

cors_origins_env = os.getenv("ORION_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
allowed_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["portfolio"])
app.include_router(risk.router, prefix="/api/v1/risk", tags=["risk"])
app.include_router(ai_council.router, prefix="/api/v1/ai-council", tags=["ai-council"])
app.include_router(execution.router, prefix="/api/v1/execution", tags=["execution"])
app.include_router(research.router, prefix="/api/v1/research", tags=["research"])
app.include_router(market_stream.router, prefix="/api/v1/ws", tags=["websocket"])
