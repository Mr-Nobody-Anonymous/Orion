import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import logging

class YahooFetcher:
    """Yahoo Finance数据获取器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def fetch_historical_data(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        interval: str = '1d'
    ) -> pd.DataFrame:
        """
        获取历史数据
        :param symbol: 股票代码 (例如: 'AAPL', 'MSFT')
        :param start_time: 开始时间
        :param end_time: 结束时间
        :param interval: 时间间隔 ('1d', '1wk', '1mo')
        :return: DataFrame包含OHLCV数据
        """
        try:
            # 如果未指定时间，默认获取过去一年的数据
            if not start_time:
                start_time = datetime.now() - timedelta(days=365)
            if not end_time:
                end_time = datetime.now()

            # 获取数据
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=start_time,
                end=end_time,
                interval=interval
            )

            # 重命名列以保持一致性
            df.columns = [x.lower() for x in df.columns]
            
            self.logger.info(f"Successfully fetched {len(df)} records for {symbol}")
            return df

        except Exception as e:
            self.logger.error(f"Error fetching data for {symbol}: {str(e)}")
            raise

    def get_company_info(self, symbol: str) -> dict:
        """获取公司信息"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return {
                'name': info.get('longName'),
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                'market_cap': info.get('marketCap'),
                'pe_ratio': info.get('trailingPE'),
                'dividend_yield': info.get('dividendYield'),
                'beta': info.get('beta')
            }
        except Exception as e:
            self.logger.error(f"Error fetching company info for {symbol}: {str(e)}")
            raise

    def get_financial_data(self, symbol: str) -> dict:
        """获取财务数据"""
        try:
            ticker = yf.Ticker(symbol)
            return {
                'balance_sheet': ticker.balance_sheet,
                'income_statement': ticker.financials,
                'cash_flow': ticker.cashflow
            }
        except Exception as e:
            self.logger.error(f"Error fetching financial data for {symbol}: {str(e)}")
            raise 