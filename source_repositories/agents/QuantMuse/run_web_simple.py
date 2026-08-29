#!/usr/bin/env python3
"""
Simple Web Server Launcher
A simplified version that doesn't require all dependencies
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from datetime import datetime
import os

# Create a simple FastAPI app
app = FastAPI(title="Trading System", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Main dashboard page"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Trading System Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/boxicons@2.0.7/css/boxicons.min.css" rel="stylesheet">
        <style>
            body { background-color: #f5f5f5; }
            .card { border: none; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .metric { margin-bottom: 15px; }
            .metric label { display: block; font-size: 12px; color: #6c757d; margin-bottom: 5px; }
            .metric span { display: block; font-size: 18px; font-weight: 600; color: #343a40; }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="#">
                    <i class='bx bx-trending-up'></i>
                    Trading System
                </a>
            </div>
        </nav>

        <div class="container-fluid mt-3">
            <div class="row">
                <div class="col-md-3">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">System Status</h5>
                            <div class="metric">
                                <label>Status</label>
                                <span style="color: #28a745;">Running</span>
                            </div>
                            <div class="metric">
                                <label>Uptime</label>
                                <span>2 days, 5 hours</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-3">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">Active Strategies</h5>
                            <div class="metric">
                                <label>Count</label>
                                <span>3</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-3">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">Total Trades</h5>
                            <div class="metric">
                                <label>Count</label>
                                <span>1,250</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-3">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">Portfolio Value</h5>
                            <div class="metric">
                                <label>Value</label>
                                <span>$125,000</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row mt-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h5>Performance Metrics</h5>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-6">
                                    <div class="metric">
                                        <label>Total Return</label>
                                        <span>25.0%</span>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="metric">
                                        <label>Sharpe Ratio</label>
                                        <span>1.8</span>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="metric">
                                        <label>Max Drawdown</label>
                                        <span>-12.0%</span>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="metric">
                                        <label>Win Rate</label>
                                        <span>65.0%</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h5>Risk Metrics</h5>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-6">
                                    <div class="metric">
                                        <label>VaR (95%)</label>
                                        <span>-2.0%</span>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="metric">
                                        <label>CVaR (95%)</label>
                                        <span>-3.0%</span>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="metric">
                                        <label>Beta</label>
                                        <span>0.85</span>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="metric">
                                        <label>Volatility</label>
                                        <span>15.0%</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row mt-4">
                <div class="col-12">
                    <div class="card">
                        <div class="card-header">
                            <h5>Welcome to Trading System Dashboard</h5>
                        </div>
                        <div class="card-body">
                            <p>This is a simplified version of the trading system dashboard.</p>
                            <p>Features available:</p>
                            <ul>
                                <li>System status monitoring</li>
                                <li>Performance metrics</li>
                                <li>Risk metrics</li>
                                <li>Portfolio overview</li>
                            </ul>
                            <p>To access the full version with all features, please install the required dependencies:</p>
                            <code>pip install -e .[web,ai,visualization]</code>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/system/status")
async def get_system_status():
    """Get system status"""
    return {
        "status": "running",
        "uptime": "2 days, 5 hours, 30 minutes",
        "active_strategies": 3,
        "total_trades": 1250,
        "system_metrics": {
            "cpu_usage": 45.2,
            "memory_usage": 2.3,
            "active_connections": 12,
            "api_calls_per_min": 156
        }
    }

if __name__ == "__main__":
    print("🚀 Starting Simple Trading System Web Interface...")
    print("📊 Web interface will be available at http://localhost:8000")
    print("⏹️  Press Ctrl+C to stop the server")
    print("-" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info") 