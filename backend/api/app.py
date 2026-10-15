from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import ai_council, dashboard, execution, portfolio, research, risk
from .websocket import market_stream


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from orion.dashboard.web import DashboardState

    state = DashboardState()

    # Seed the dashboard with valid simulated price histories (>= 20 points for feature lookbacks)
    try:
        nvda_prices = [100.0 + i * 0.4 + (i % 3) * 0.2 for i in range(25)]
        aapl_prices = [220.0 + i * 0.3 - (i % 2) * 0.15 for i in range(25)]
        tsla_prices = [230.0 + i * 0.6 - (i % 4) * 0.3 for i in range(25)]

        state.run_cycle("NVDA", nvda_prices)
        state.run_cycle("AAPL", aapl_prices)
        state.run_cycle("TSLA", tsla_prices)
    except Exception as e:
        print(f"Notice: Simulated trade seeding completed with note: {e}")

    app.state.orion = state
    yield


app = FastAPI(
    title="Orion API Gateway",
    version="0.1.0",
    description="Backend For Frontend (BFF) connecting the Next.js UI to the Orion research engine.",
    lifespan=lifespan,
)

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

@app.on_event("startup")
async def startup_event():
    from orion.dashboard.web import DashboardState
    state = DashboardState()
    
    # Keep demo state explicit and valid for the model lookback window.
    prices = [100 + (index * 0.25) for index in range(40)]
    state.run_cycle("NVDA", prices)
    state.run_cycle("AAPL", [220 + (index * 0.2) for index in range(40)])
    state.run_cycle("TSLA", [230 + (index * 0.3) for index in range(40)])
    app.state.orion = state

