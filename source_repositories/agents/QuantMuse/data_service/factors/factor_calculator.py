import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Union
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass

@dataclass
class FactorData:
    """Factor data structure"""
    symbol: str
    date: datetime
    factor_name: str
    factor_value: float
    rank: Optional[int] = None
    percentile: Optional[float] = None

class FactorCalculator:
    """Quantitative factor calculator for stock analysis"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Define factor categories
        self.factor_categories = {
            'momentum': ['price_momentum', 'volume_momentum', 'relative_strength'],
            'value': ['pe_ratio', 'pb_ratio', 'ps_ratio', 'dividend_yield'],
            'quality': ['roe', 'roa', 'debt_to_equity', 'current_ratio'],
            'size': ['market_cap', 'enterprise_value'],
            'volatility': ['price_volatility', 'beta', 'sharpe_ratio'],
            'technical': ['rsi', 'macd', 'bollinger_bands', 'moving_averages']
        }
    
    def calculate_price_momentum(self, prices: pd.Series, periods: List[int] = [20, 60, 252]) -> Dict[str, float]:
        """Calculate price momentum factors"""
        factors = {}
        
        for period in periods:
            if len(prices) >= period:
                # Simple momentum
                momentum = (prices.iloc[-1] / prices.iloc[-period] - 1) * 100
                factors[f'momentum_{period}d'] = momentum
                
                # Relative momentum (vs market)
                # This would need market data for comparison
                
                # Momentum acceleration
                if len(prices) >= period * 2:
                    momentum_1 = (prices.iloc[-period] / prices.iloc[-period*2] - 1) * 100
                    momentum_2 = (prices.iloc[-1] / prices.iloc[-period] - 1) * 100
                    acceleration = momentum_2 - momentum_1
                    factors[f'momentum_accel_{period}d'] = acceleration
        
        return factors
    
    def calculate_volume_momentum(self, prices: pd.Series, volumes: pd.Series, 
                                periods: List[int] = [20, 60]) -> Dict[str, float]:
        """Calculate volume momentum factors"""
        factors = {}
        
        for period in periods:
            if len(volumes) >= period:
                # Volume momentum
                volume_momentum = (volumes.iloc[-period:].mean() / volumes.iloc[-period*2:-period].mean() - 1) * 100
                factors[f'volume_momentum_{period}d'] = volume_momentum
                
                # Volume-price trend
                if len(prices) >= period:
                    price_change = (prices.iloc[-1] / prices.iloc[-period] - 1) * 100
                    volume_price_trend = volume_momentum * price_change
                    factors[f'volume_price_trend_{period}d'] = volume_price_trend
        
        return factors
    
    def calculate_relative_strength(self, prices: pd.Series, market_prices: pd.Series, 
                                  period: int = 252) -> float:
        """Calculate relative strength vs market"""
        if len(prices) >= period and len(market_prices) >= period:
            stock_return = (prices.iloc[-1] / prices.iloc[-period] - 1) * 100
            market_return = (market_prices.iloc[-1] / market_prices.iloc[-period] - 1) * 100
            relative_strength = stock_return - market_return
            return relative_strength
        return 0.0
    
    def calculate_value_factors(self, financial_data: Dict[str, float]) -> Dict[str, float]:
        """Calculate value factors from financial data"""
        factors = {}
        
        # P/E Ratio
        if financial_data.get('price') and financial_data.get('eps'):
            pe_ratio = financial_data['price'] / financial_data['eps']
            factors['pe_ratio'] = pe_ratio
        
        # P/B Ratio
        if financial_data.get('price') and financial_data.get('book_value_per_share'):
            pb_ratio = financial_data['price'] / financial_data['book_value_per_share']
            factors['pb_ratio'] = pb_ratio
        
        # P/S Ratio
        if financial_data.get('price') and financial_data.get('revenue_per_share'):
            ps_ratio = financial_data['price'] / financial_data['revenue_per_share']
            factors['ps_ratio'] = ps_ratio
        
        # Dividend Yield
        if financial_data.get('price') and financial_data.get('dividend_per_share'):
            dividend_yield = (financial_data['dividend_per_share'] / financial_data['price']) * 100
            factors['dividend_yield'] = dividend_yield
        
        # EV/EBITDA
        if financial_data.get('enterprise_value') and financial_data.get('ebitda'):
            ev_ebitda = financial_data['enterprise_value'] / financial_data['ebitda']
            factors['ev_ebitda'] = ev_ebitda
        
        return factors
    
    def calculate_quality_factors(self, financial_data: Dict[str, float]) -> Dict[str, float]:
        """Calculate quality factors from financial data"""
        factors = {}
        
        # Return on Equity (ROE)
        if financial_data.get('net_income') and financial_data.get('shareholders_equity'):
            roe = (financial_data['net_income'] / financial_data['shareholders_equity']) * 100
            factors['roe'] = roe
        
        # Return on Assets (ROA)
        if financial_data.get('net_income') and financial_data.get('total_assets'):
            roa = (financial_data['net_income'] / financial_data['total_assets']) * 100
            factors['roa'] = roa
        
        # Debt to Equity Ratio
        if financial_data.get('total_debt') and financial_data.get('shareholders_equity'):
            debt_to_equity = financial_data['total_debt'] / financial_data['shareholders_equity']
            factors['debt_to_equity'] = debt_to_equity
        
        # Current Ratio
        if financial_data.get('current_assets') and financial_data.get('current_liabilities'):
            current_ratio = financial_data['current_assets'] / financial_data['current_liabilities']
            factors['current_ratio'] = current_ratio
        
        # Gross Margin
        if financial_data.get('gross_profit') and financial_data.get('revenue'):
            gross_margin = (financial_data['gross_profit'] / financial_data['revenue']) * 100
            factors['gross_margin'] = gross_margin
        
        # Operating Margin
        if financial_data.get('operating_income') and financial_data.get('revenue'):
            operating_margin = (financial_data['operating_income'] / financial_data['revenue']) * 100
            factors['operating_margin'] = operating_margin
        
        return factors
    
    def calculate_size_factors(self, market_data: Dict[str, float]) -> Dict[str, float]:
        """Calculate size factors"""
        factors = {}
        
        # Market Cap
        if market_data.get('market_cap'):
            factors['market_cap'] = market_data['market_cap']
            
            # Market cap categories
            if market_data['market_cap'] > 10000000000:  # > $10B
                factors['market_cap_category'] = 'large'
            elif market_data['market_cap'] > 2000000000:  # > $2B
                factors['market_cap_category'] = 'mid'
            else:
                factors['market_cap_category'] = 'small'
        
        # Enterprise Value
        if market_data.get('enterprise_value'):
            factors['enterprise_value'] = market_data['enterprise_value']
        
        return factors
    
    def calculate_volatility_factors(self, prices: pd.Series, 
                                   risk_free_rate: float = 0.02) -> Dict[str, float]:
        """Calculate volatility and risk factors"""
        factors = {}
        
        if len(prices) < 30:
            return factors
        
        # Calculate returns
        returns = prices.pct_change().dropna()
        
        # Price volatility (annualized)
        volatility = returns.std() * np.sqrt(252) * 100
        factors['price_volatility'] = volatility
        
        # Beta (would need market data)
        # factors['beta'] = self._calculate_beta(returns, market_returns)
        
        # Sharpe ratio
        if volatility > 0:
            excess_return = returns.mean() * 252 - risk_free_rate
            sharpe_ratio = excess_return / volatility
            factors['sharpe_ratio'] = sharpe_ratio
        
        # Maximum drawdown
        cumulative_returns = (1 + returns).cumprod()
        rolling_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - rolling_max) / rolling_max
        max_drawdown = drawdown.min() * 100
        factors['max_drawdown'] = max_drawdown
        
        # Value at Risk (VaR)
        var_95 = np.percentile(returns, 5) * 100
        factors['var_95'] = var_95
        
        return factors
    
    def calculate_technical_factors(self, prices: pd.Series, 
                                  volumes: pd.Series = None) -> Dict[str, float]:
        """Calculate technical indicators"""
        factors = {}
        
        if len(prices) < 14:
            return factors
        
        # RSI
        rsi = self._calculate_rsi(prices, period=14)
        factors['rsi'] = rsi
        
        # MACD
        macd, signal = self._calculate_macd(prices)
        factors['macd'] = macd
        factors['macd_signal'] = signal
        factors['macd_histogram'] = macd - signal
        
        # Moving averages
        ma_20 = prices.rolling(20).mean().iloc[-1]
        ma_50 = prices.rolling(50).mean().iloc[-1]
        ma_200 = prices.rolling(200).mean().iloc[-1]
        
        factors['ma_20'] = ma_20
        factors['ma_50'] = ma_50
        factors['ma_200'] = ma_200
        
        # Price vs moving averages
        current_price = prices.iloc[-1]
        factors['price_vs_ma20'] = (current_price / ma_20 - 1) * 100
        factors['price_vs_ma50'] = (current_price / ma_50 - 1) * 100
        factors['price_vs_ma200'] = (current_price / ma_200 - 1) * 100
        
        # Bollinger Bands
        bb_upper, bb_lower = self._calculate_bollinger_bands(prices)
        factors['bb_upper'] = bb_upper
        factors['bb_lower'] = bb_lower
        factors['bb_position'] = (current_price - bb_lower) / (bb_upper - bb_lower)
        
        return factors
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI indicator"""
        if len(prices) < period + 1:
            return 50.0
        
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1]
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
        """Calculate MACD indicator"""
        if len(prices) < slow:
            return 0.0, 0.0
        
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        
        return macd_line.iloc[-1], signal_line.iloc[-1]
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: int = 2) -> tuple:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            return prices.iloc[-1], prices.iloc[-1]
        
        sma = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return upper_band.iloc[-1], lower_band.iloc[-1]
    
    def calculate_all_factors(self, symbol: str, 
                            prices: pd.Series,
                            volumes: pd.Series = None,
                            financial_data: Dict[str, float] = None,
                            market_data: Dict[str, float] = None,
                            market_prices: pd.Series = None) -> Dict[str, float]:
        """Calculate all available factors for a symbol"""
        all_factors = {}
        
        # Price and volume data factors
        if prices is not None:
            all_factors.update(self.calculate_price_momentum(prices))
            all_factors.update(self.calculate_volatility_factors(prices))
            all_factors.update(self.calculate_technical_factors(prices, volumes))
            
            if volumes is not None:
                all_factors.update(self.calculate_volume_momentum(prices, volumes))
            
            if market_prices is not None:
                all_factors['relative_strength'] = self.calculate_relative_strength(prices, market_prices)
        
        # Financial data factors
        if financial_data is not None:
            all_factors.update(self.calculate_value_factors(financial_data))
            all_factors.update(self.calculate_quality_factors(financial_data))
        
        # Market data factors
        if market_data is not None:
            all_factors.update(self.calculate_size_factors(market_data))
        
        # Add metadata
        all_factors['symbol'] = symbol
        all_factors['calculation_date'] = datetime.now()
        
        return all_factors
    
    def rank_factors(self, factor_data: List[FactorData]) -> List[FactorData]:
        """Rank factors by value"""
        if not factor_data:
            return factor_data
        
        # Group by factor name
        factor_groups = {}
        for data in factor_data:
            if data.factor_name not in factor_groups:
                factor_groups[data.factor_name] = []
            factor_groups[data.factor_name].append(data)
        
        # Rank each factor group
        ranked_data = []
        for factor_name, group in factor_groups.items():
            # Sort by factor value
            sorted_group = sorted(group, key=lambda x: x.factor_value, reverse=True)
            
            # Assign ranks and percentiles
            for i, data in enumerate(sorted_group):
                data.rank = i + 1
                data.percentile = (i + 1) / len(sorted_group) * 100
                ranked_data.append(data)
        
        return ranked_data 