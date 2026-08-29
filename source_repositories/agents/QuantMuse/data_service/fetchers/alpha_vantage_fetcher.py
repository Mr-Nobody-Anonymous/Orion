from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.fundamentaldata import FundamentalData
import pandas as pd
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from ..utils.exceptions import DataFetchError

class AlphaVantageFetcher:
    """Alpha Vantage数据获取器"""
    
    def __init__(self, api_key: str):
        """
        初始化Alpha Vantage客户端
        :param api_key: Alpha Vantage API key
        """
        self.logger = logging.getLogger(__name__)
        try:
            self.ts = TimeSeries(key=api_key, output_format='pandas')
            self.fd = FundamentalData(key=api_key, output_format='pandas')
            self.logger.info("Alpha Vantage fetcher initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Alpha Vantage client: {str(e)}")
            raise

    def fetch_historical_data(
        self,
        symbol: str,
        interval: str = 'daily',
        outputsize: str = 'compact'
    ) -> pd.DataFrame:
        """
        获取历史数据
        :param symbol: 股票代码
        :param interval: 时间间隔 (intraday, daily, weekly, monthly)
        :param outputsize: 数据量 (compact or full)
        :return: DataFrame包含OHLCV数据
        """
        try:
            if interval == 'intraday':
                data, meta_data = self.ts.get_intraday(
                    symbol=symbol,
                    interval='60min',
                    outputsize=outputsize
                )
            elif interval == 'daily':
                data, meta_data = self.ts.get_daily(
                    symbol=symbol,
                    outputsize=outputsize
                )
            elif interval == 'weekly':
                data, meta_data = self.ts.get_weekly(symbol=symbol)
            elif interval == 'monthly':
                data, meta_data = self.ts.get_monthly(symbol=symbol)
            else:
                raise ValueError(f"Invalid interval: {interval}")
            
            # 重命名列
            data.columns = ['open', 'high', 'low', 'close', 'volume']
            
            self.logger.info(f"Successfully fetched {len(data)} records for {symbol}")
            return data
            
        except Exception as e:
            self.logger.error(f"Error fetching historical data: {str(e)}")
            raise DataFetchError(f"Failed to fetch historical data: {str(e)}")

    def get_company_overview(self, symbol: str) -> Dict[str, Any]:
        """
        获取公司概况
        :param symbol: 股票代码
        :return: 公司基本信息
        """
        try:
            overview, _ = self.fd.get_company_overview(symbol)
            return overview.to_dict()
        except Exception as e:
            self.logger.error(f"Error fetching company overview: {str(e)}")
            raise DataFetchError(f"Failed to fetch company overview: {str(e)}")

    def get_income_statement(self, symbol: str) -> pd.DataFrame:
        """
        获取收益表
        :param symbol: 股票代码
        :return: 收益表数据
        """
        try:
            income_stmt, _ = self.fd.get_income_statement_annual(symbol)
            return income_stmt
        except Exception as e:
            self.logger.error(f"Error fetching income statement: {str(e)}")
            raise DataFetchError(f"Failed to fetch income statement: {str(e)}")

    def get_balance_sheet(self, symbol: str) -> pd.DataFrame:
        """
        获取资产负债表
        :param symbol: 股票代码
        :return: 资产负债表数据
        """
        try:
            balance_sheet, _ = self.fd.get_balance_sheet_annual(symbol)
            return balance_sheet
        except Exception as e:
            self.logger.error(f"Error fetching balance sheet: {str(e)}")
            raise DataFetchError(f"Failed to fetch balance sheet: {str(e)}")

    def get_cash_flow(self, symbol: str) -> pd.DataFrame:
        """
        获取现金流量表
        :param symbol: 股票代码
        :return: 现金流量表数据
        """
        try:
            cash_flow, _ = self.fd.get_cash_flow_annual(symbol)
            return cash_flow
        except Exception as e:
            self.logger.error(f"Error fetching cash flow: {str(e)}")
            raise DataFetchError(f"Failed to fetch cash flow: {str(e)}") 