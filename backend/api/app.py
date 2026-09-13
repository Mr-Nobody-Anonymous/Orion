from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import dashboard, portfolio, risk, ai_council, execution, research
from .websocket import market_stream

app = FastAPI(
    title="Orion API Gateway",
    version="1.0.0",
    description="Backend For Frontend (BFF) connecting the Next.js UI to Orion core.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
    
    # Seed the dashboard with a few initial simulated trades so it isn't completely empty
    try:
        prices = [100, 101, 100.5, 102, 103, 104, 105]
        state.run_cycle("NVDA", prices)
        state.run_cycle("AAPL", [220, 221, 222, 224])
        state.run_cycle("TSLA", [230, 235, 240, 238])
    except Exception as e:
        print(f"Warning: Failed to seed simulated trades: {e}")
        
    app.state.orion = state
