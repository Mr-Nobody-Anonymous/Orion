"""Federal Reserve Economic Data (FRED) live macroeconomic provider."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from .base import LiveMacroMetric


class FredLiveProvider:
    """Federal Reserve Economic Data (FRED) yield curve and macroeconomic metrics provider."""

    SERIES_NAMES = {
        "DGS10": "US 10-Year Treasury Constant Maturity",
        "DGS2": "US 2-Year Treasury Constant Maturity",
        "DGS3MO": "US 3-Month Treasury Bill Secondary Market",
        "DGS30": "US 30-Year Treasury Constant Maturity",
        "FEDFUNDS": "Federal Funds Effective Rate",
        "CPIAUCSL": "Consumer Price Index for All Urban Consumers",
        "UNRATE": "Unemployment Rate",
        "GDP": "Gross Domestic Product",
    }

    def __init__(self, api_key: str | None = None, timeout_seconds: float = 5.0) -> None:
        self.api_key = api_key or os.environ.get("FRED_API_KEY")
        self.timeout = timeout_seconds

    def fetch_series(self, series_id: str) -> LiveMacroMetric | None:
        """Fetch latest observation for a FRED series."""
        if not self.api_key:
            return None

        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={self.api_key}&file_type=json&sort_order=desc&limit=2"
        req = urllib.request.Request(url, headers={"User-Agent": "OrionFinancialOS/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            obs = data.get("observations", [])
            if not obs:
                return None

            curr_val = float(obs[0].get("value", 0.0))
            prior_val = float(obs[1].get("value", curr_val)) if len(obs) > 1 else curr_val
            date_str = obs[0].get("date", "")

            return LiveMacroMetric(
                series_id=series_id,
                name=self.SERIES_NAMES.get(series_id, series_id),
                current_value=curr_val,
                prior_value=prior_val,
                unit="Percent" if "DGS" in series_id or series_id in ("FEDFUNDS", "UNRATE") else "Index",
                last_updated=date_str,
                provider_name="FRED (St. Louis Fed)",
                is_live=True,
            )
        except Exception:
            return None
