#!/usr/bin/env python3
"""
Feature Engineering for Trading ML Models
Creates technical indicators, statistical features, and engineered features
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass

try:
    from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
    from sklearn.decomposition import PCA
    from sklearn.feature_selection import SelectKBest, f_regression, f_classif
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

@dataclass
class FeatureConfig:
    """Feature engineering configuration"""
    technical_indicators: bool = True
    statistical_features: bool = True
    lag_features: bool = True
    rolling_features: bool = True
    interaction_features: bool = False
    pca_features: bool = False
    feature_selection: bool = False
    n_lags: int = 5
    n_rolling_windows: List[int] = None
    n_pca_components: int = 10
    n_select_features: int = 20

class FeatureEngineer:
    """Feature engineering for trading data"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.scaler = None
        self.pca = None
        self.feature_selector = None
        self.feature_names = []
        
        if not SKLEARN_AVAILABLE:
            self.logger.warning("Scikit-learn not available for advanced feature engineering")
    
    def create_technical_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create technical indicators"""
        df = data.copy()
        
        # Price-based indicators
        if 'close' in df.columns:
            # Moving averages
            df['sma_5'] = df['close'].rolling(5).mean()
            df['sma_10'] = df['close'].rolling(10).mean()
            df['sma_20'] = df['close'].rolling(20).mean()
            df['sma_50'] = df['close'].rolling(50).mean()
            
            # Exponential moving averages
            df['ema_5'] = df['close'].ewm(span=5).mean()
            df['ema_10'] = df['close'].ewm(span=10).mean()
            df['ema_20'] = df['close'].ewm(span=20).mean()
            
            # Price vs moving averages
            df['price_vs_sma_20'] = (df['close'] / df['sma_20'] - 1) * 100
            df['price_vs_ema_20'] = (df['close'] / df['ema_20'] - 1) * 100
            
            # RSI
            df['rsi'] = self._calculate_rsi(df['close'])
            
            # MACD
            df['macd'], df['macd_signal'], df['macd_hist'] = self._calculate_macd(df['close'])
            
            # Bollinger Bands
            df['bb_upper'], df['bb_middle'], df['bb_lower'] = self._calculate_bollinger_bands(df['close'])
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
            
            # Stochastic Oscillator
            df['stoch_k'], df['stoch_d'] = self._calculate_stochastic(df)
            
            # Williams %R
            df['williams_r'] = self._calculate_williams_r(df)
            
            # Commodity Channel Index
            df['cci'] = self._calculate_cci(df)
            
            # Average True Range
            df['atr'] = self._calculate_atr(df)
            
            # Parabolic SAR
            df['psar'] = self._calculate_psar(df)
        
        # Volume-based indicators
        if 'volume' in df.columns:
            # Volume moving averages
            df['volume_sma_5'] = df['volume'].rolling(5).mean()
            df['volume_sma_20'] = df['volume'].rolling(20).mean()
            
            # Volume ratio
            df['volume_ratio'] = df['volume'] / df['volume_sma_20']
            
            # On-Balance Volume
            df['obv'] = self._calculate_obv(df)
            
            # Volume Price Trend
            df['vpt'] = self._calculate_vpt(df)
            
            # Money Flow Index
            df['mfi'] = self._calculate_mfi(df)
        
        # Momentum indicators
        if 'close' in df.columns:
            # Rate of Change
            df['roc_5'] = df['close'].pct_change(5) * 100
            df['roc_10'] = df['close'].pct_change(10) * 100
            df['roc_20'] = df['close'].pct_change(20) * 100
            
            # Momentum
            df['momentum_5'] = df['close'] - df['close'].shift(5)
            df['momentum_10'] = df['close'] - df['close'].shift(10)
            
            # Price Rate of Change
            df['proc'] = (df['close'] / df['close'].shift(1) - 1) * 100
        
        return df
    
    def create_statistical_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create statistical features"""
        df = data.copy()
        
        if 'close' in df.columns:
            returns = df['close'].pct_change().dropna()
            
            # Rolling statistics
            for window in [5, 10, 20]:
                df[f'returns_mean_{window}'] = returns.rolling(window).mean()
                df[f'returns_std_{window}'] = returns.rolling(window).std()
                df[f'returns_skew_{window}'] = returns.rolling(window).skew()
                df[f'returns_kurt_{window}'] = returns.rolling(window).kurt()
                
                # Volatility
                df[f'volatility_{window}'] = returns.rolling(window).std() * np.sqrt(252)
                
                # Sharpe ratio (assuming risk-free rate = 0)
                df[f'sharpe_{window}'] = df[f'returns_mean_{window}'] / df[f'returns_std_{window}']
            
            # Rolling quantiles
            for window in [10, 20]:
                df[f'returns_q25_{window}'] = returns.rolling(window).quantile(0.25)
                df[f'returns_q75_{window}'] = returns.rolling(window).quantile(0.75)
                df[f'returns_iqr_{window}'] = df[f'returns_q75_{window}'] - df[f'returns_q25_{window}']
            
            # Rolling min/max
            for window in [10, 20]:
                df[f'returns_min_{window}'] = returns.rolling(window).min()
                df[f'returns_max_{window}'] = returns.rolling(window).max()
                df[f'returns_range_{window}'] = df[f'returns_max_{window}'] - df[f'returns_min_{window}']
        
        return df
    
    def create_lag_features(self, data: pd.DataFrame, n_lags: int = 5) -> pd.DataFrame:
        """Create lag features"""
        df = data.copy()
        
        # Price lags
        if 'close' in df.columns:
            for lag in range(1, n_lags + 1):
                df[f'close_lag_{lag}'] = df['close'].shift(lag)
                df[f'returns_lag_{lag}'] = df['close'].pct_change().shift(lag)
        
        # Volume lags
        if 'volume' in df.columns:
            for lag in range(1, n_lags + 1):
                df[f'volume_lag_{lag}'] = df['volume'].shift(lag)
        
        # Technical indicator lags
        tech_indicators = ['rsi', 'macd', 'bb_position', 'stoch_k', 'williams_r']
        for indicator in tech_indicators:
            if indicator in df.columns:
                for lag in range(1, n_lags + 1):
                    df[f'{indicator}_lag_{lag}'] = df[indicator].shift(lag)
        
        return df
    
    def create_rolling_features(self, data: pd.DataFrame, 
                              windows: List[int] = None) -> pd.DataFrame:
        """Create rolling window features"""
        df = data.copy()
        
        if windows is None:
            windows = [5, 10, 20, 50]
        
        # Rolling statistics for price
        if 'close' in df.columns:
            for window in windows:
                df[f'close_rolling_mean_{window}'] = df['close'].rolling(window).mean()
                df[f'close_rolling_std_{window}'] = df['close'].rolling(window).std()
                df[f'close_rolling_min_{window}'] = df['close'].rolling(window).min()
                df[f'close_rolling_max_{window}'] = df['close'].rolling(window).max()
                
                # Rolling percentiles
                df[f'close_rolling_p25_{window}'] = df['close'].rolling(window).quantile(0.25)
                df[f'close_rolling_p75_{window}'] = df['close'].rolling(window).quantile(0.75)
        
        # Rolling statistics for volume
        if 'volume' in df.columns:
            for window in windows:
                df[f'volume_rolling_mean_{window}'] = df['volume'].rolling(window).mean()
                df[f'volume_rolling_std_{window}'] = df['volume'].rolling(window).std()
        
        return df
    
    def create_interaction_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create interaction features"""
        df = data.copy()
        
        # Price-volume interactions
        if 'close' in df.columns and 'volume' in df.columns:
            df['price_volume'] = df['close'] * df['volume']
            df['price_volume_ratio'] = df['close'] / df['volume']
            
            # Price-volume trend
            df['pvt'] = (df['close'] - df['close'].shift(1)) * df['volume']
            df['pvt_cumsum'] = df['pvt'].cumsum()
        
        # Technical indicator interactions
        if 'rsi' in df.columns and 'macd' in df.columns:
            df['rsi_macd'] = df['rsi'] * df['macd']
            df['rsi_macd_ratio'] = df['rsi'] / (df['macd'] + 1e-8)
        
        if 'bb_position' in df.columns and 'rsi' in df.columns:
            df['bb_rsi'] = df['bb_position'] * df['rsi']
        
        return df
    
    def scale_features(self, data: pd.DataFrame, method: str = 'standard') -> pd.DataFrame:
        """Scale features"""
        if not SKLEARN_AVAILABLE:
            return data
        
        df = data.copy()
        
        # Select numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        feature_cols = [col for col in numeric_cols if col not in ['close', 'open', 'high', 'low', 'volume']]
        
        if not feature_cols:
            return df
        
        # Create scaler
        if method == 'standard':
            self.scaler = StandardScaler()
        elif method == 'minmax':
            self.scaler = MinMaxScaler()
        elif method == 'robust':
            self.scaler = RobustScaler()
        else:
            raise ValueError(f"Unknown scaling method: {method}")
        
        # Scale features
        df_scaled = df.copy()
        df_scaled[feature_cols] = self.scaler.fit_transform(df[feature_cols])
        
        return df_scaled
    
    def apply_pca(self, data: pd.DataFrame, n_components: int = 10) -> pd.DataFrame:
        """Apply PCA for dimensionality reduction"""
        if not SKLEARN_AVAILABLE:
            return data
        
        df = data.copy()
        
        # Select numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        feature_cols = [col for col in numeric_cols if col not in ['close', 'open', 'high', 'low', 'volume']]
        
        if len(feature_cols) < n_components:
            return df
        
        # Apply PCA
        self.pca = PCA(n_components=n_components)
        pca_features = self.pca.fit_transform(df[feature_cols])
        
        # Create new dataframe with PCA features
        pca_df = pd.DataFrame(pca_features, 
                             columns=[f'pca_{i+1}' for i in range(n_components)],
                             index=df.index)
        
        # Combine with original data
        result_df = pd.concat([df, pca_df], axis=1)
        
        return result_df
    
    def select_features(self, data: pd.DataFrame, target: pd.Series, 
                       n_features: int = 20, method: str = 'f_regression') -> pd.DataFrame:
        """Select best features"""
        if not SKLEARN_AVAILABLE:
            return data
        
        df = data.copy()
        
        # Select numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        feature_cols = [col for col in numeric_cols if col not in ['close', 'open', 'high', 'low', 'volume']]
        
        if len(feature_cols) < n_features:
            return df
        
        # Remove rows with NaN values
        valid_idx = ~(df[feature_cols].isna().any(axis=1) | target.isna())
        X = df[feature_cols].loc[valid_idx]
        y = target.loc[valid_idx]
        
        # Select scoring function
        if method == 'f_regression':
            scoring_func = f_regression
        elif method == 'f_classif':
            scoring_func = f_classif
        else:
            raise ValueError(f"Unknown feature selection method: {method}")
        
        # Apply feature selection
        self.feature_selector = SelectKBest(score_func=scoring_func, k=n_features)
        X_selected = self.feature_selector.fit_transform(X, y)
        
        # Get selected feature names
        selected_features = X.columns[self.feature_selector.get_support()].tolist()
        
        # Create result dataframe
        result_df = df[selected_features].copy()
        
        return result_df
    
    def engineer_features(self, data: pd.DataFrame, config: FeatureConfig = None) -> pd.DataFrame:
        """Complete feature engineering pipeline"""
        if config is None:
            config = FeatureConfig()
        
        df = data.copy()
        
        # Create technical indicators
        if config.technical_indicators:
            df = self.create_technical_indicators(df)
        
        # Create statistical features
        if config.statistical_features:
            df = self.create_statistical_features(df)
        
        # Create lag features
        if config.lag_features:
            df = self.create_lag_features(df, config.n_lags)
        
        # Create rolling features
        if config.rolling_features:
            df = self.create_rolling_features(df, config.n_rolling_windows)
        
        # Create interaction features
        if config.interaction_features:
            df = self.create_interaction_features(df)
        
        # Apply PCA
        if config.pca_features and SKLEARN_AVAILABLE:
            df = self.apply_pca(df, config.n_pca_components)
        
        # Store feature names
        self.feature_names = df.columns.tolist()
        
        return df
    
    # Technical indicator calculation methods
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD"""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal).mean()
        macd_hist = macd - macd_signal
        return macd, macd_signal, macd_hist
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: int = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands"""
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return upper, middle, lower
    
    def _calculate_stochastic(self, data: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        """Calculate Stochastic Oscillator"""
        if 'high' not in data.columns or 'low' not in data.columns or 'close' not in data.columns:
            return pd.Series(), pd.Series()
        
        lowest_low = data['low'].rolling(window=k_period).min()
        highest_high = data['high'].rolling(window=k_period).max()
        
        k = 100 * ((data['close'] - lowest_low) / (highest_high - lowest_low))
        d = k.rolling(window=d_period).mean()
        
        return k, d
    
    def _calculate_williams_r(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Williams %R"""
        if 'high' not in data.columns or 'low' not in data.columns or 'close' not in data.columns:
            return pd.Series()
        
        highest_high = data['high'].rolling(window=period).max()
        lowest_low = data['low'].rolling(window=period).min()
        
        williams_r = -100 * ((highest_high - data['close']) / (highest_high - lowest_low))
        return williams_r
    
    def _calculate_cci(self, data: pd.DataFrame, period: int = 20) -> pd.Series:
        """Calculate Commodity Channel Index"""
        if 'high' not in data.columns or 'low' not in data.columns or 'close' not in data.columns:
            return pd.Series()
        
        typical_price = (data['high'] + data['low'] + data['close']) / 3
        sma_tp = typical_price.rolling(window=period).mean()
        mad = typical_price.rolling(window=period).apply(lambda x: np.mean(np.abs(x - x.mean())))
        
        cci = (typical_price - sma_tp) / (0.015 * mad)
        return cci
    
    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        if 'high' not in data.columns or 'low' not in data.columns or 'close' not in data.columns:
            return pd.Series()
        
        high_low = data['high'] - data['low']
        high_close = np.abs(data['high'] - data['close'].shift())
        low_close = np.abs(data['low'] - data['close'].shift())
        
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        atr = true_range.rolling(window=period).mean()
        
        return atr
    
    def _calculate_psar(self, data: pd.DataFrame, acceleration: float = 0.02, maximum: float = 0.2) -> pd.Series:
        """Calculate Parabolic SAR"""
        if 'high' not in data.columns or 'low' not in data.columns:
            return pd.Series()
        
        psar = pd.Series(index=data.index, dtype=float)
        af = acceleration
        ep = data['low'].iloc[0]
        long = True
        
        for i in range(1, len(data)):
            if long:
                psar.iloc[i] = psar.iloc[i-1] + af * (ep - psar.iloc[i-1])
                if data['low'].iloc[i] < psar.iloc[i]:
                    long = False
                    psar.iloc[i] = ep
                    ep = data['high'].iloc[i]
                    af = acceleration
                else:
                    if data['high'].iloc[i] > ep:
                        ep = data['high'].iloc[i]
                        af = min(af + acceleration, maximum)
            else:
                psar.iloc[i] = psar.iloc[i-1] + af * (ep - psar.iloc[i-1])
                if data['high'].iloc[i] > psar.iloc[i]:
                    long = True
                    psar.iloc[i] = ep
                    ep = data['low'].iloc[i]
                    af = acceleration
                else:
                    if data['low'].iloc[i] < ep:
                        ep = data['low'].iloc[i]
                        af = min(af + acceleration, maximum)
        
        return psar
    
    def _calculate_obv(self, data: pd.DataFrame) -> pd.Series:
        """Calculate On-Balance Volume"""
        if 'close' not in data.columns or 'volume' not in data.columns:
            return pd.Series()
        
        obv = pd.Series(index=data.index, dtype=float)
        obv.iloc[0] = data['volume'].iloc[0]
        
        for i in range(1, len(data)):
            if data['close'].iloc[i] > data['close'].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + data['volume'].iloc[i]
            elif data['close'].iloc[i] < data['close'].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - data['volume'].iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]
        
        return obv
    
    def _calculate_vpt(self, data: pd.DataFrame) -> pd.Series:
        """Calculate Volume Price Trend"""
        if 'close' not in data.columns or 'volume' not in data.columns:
            return pd.Series()
        
        price_change = data['close'].pct_change()
        vpt = (price_change * data['volume']).cumsum()
        return vpt
    
    def _calculate_mfi(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Money Flow Index"""
        if 'high' not in data.columns or 'low' not in data.columns or 'close' not in data.columns or 'volume' not in data.columns:
            return pd.Series()
        
        typical_price = (data['high'] + data['low'] + data['close']) / 3
        money_flow = typical_price * data['volume']
        
        positive_flow = pd.Series(0, index=data.index)
        negative_flow = pd.Series(0, index=data.index)
        
        for i in range(1, len(data)):
            if typical_price.iloc[i] > typical_price.iloc[i-1]:
                positive_flow.iloc[i] = money_flow.iloc[i]
            elif typical_price.iloc[i] < typical_price.iloc[i-1]:
                negative_flow.iloc[i] = money_flow.iloc[i]
        
        positive_mf = positive_flow.rolling(window=period).sum()
        negative_mf = negative_flow.rolling(window=period).sum()
        
        mfi = 100 - (100 / (1 + positive_mf / negative_mf))
        return mfi 