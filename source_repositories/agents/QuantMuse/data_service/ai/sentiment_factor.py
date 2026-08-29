import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass

@dataclass
class SentimentFactor:
    """Sentiment factor data structure"""
    symbol: str
    timestamp: datetime
    sentiment_score: float
    sentiment_momentum: float
    sentiment_volatility: float
    news_volume: int
    social_volume: int
    sentiment_consensus: float
    market_sentiment: float
    sector_sentiment: float
    confidence: float

class SentimentFactorCalculator:
    """Calculate sentiment-based factors for trading strategies"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def calculate_sentiment_factors(self, 
                                  sentiment_data: pd.DataFrame,
                                  symbol: str,
                                  lookback_period: int = 20) -> SentimentFactor:
        """Calculate sentiment factors for a symbol"""
        try:
            # Filter data for the symbol
            symbol_data = sentiment_data[sentiment_data['symbol'] == symbol].copy()
            
            if symbol_data.empty:
                return self._create_default_sentiment_factor(symbol)
            
            # Sort by timestamp
            symbol_data = symbol_data.sort_values('timestamp')
            
            # Calculate sentiment score (weighted average)
            sentiment_score = self._calculate_weighted_sentiment(symbol_data)
            
            # Calculate sentiment momentum
            sentiment_momentum = self._calculate_sentiment_momentum(symbol_data, lookback_period)
            
            # Calculate sentiment volatility
            sentiment_volatility = self._calculate_sentiment_volatility(symbol_data, lookback_period)
            
            # Calculate news volume
            news_volume = len(symbol_data[symbol_data['source'] == 'news'])
            
            # Calculate social volume
            social_volume = len(symbol_data[symbol_data['source'].isin(['twitter', 'reddit'])])
            
            # Calculate sentiment consensus
            sentiment_consensus = self._calculate_sentiment_consensus(symbol_data)
            
            # Calculate market sentiment (relative to market)
            market_sentiment = self._calculate_market_relative_sentiment(symbol_data, sentiment_data)
            
            # Calculate sector sentiment
            sector_sentiment = self._calculate_sector_sentiment(symbol_data, sentiment_data)
            
            # Calculate confidence
            confidence = self._calculate_confidence(symbol_data)
            
            return SentimentFactor(
                symbol=symbol,
                timestamp=datetime.now(),
                sentiment_score=sentiment_score,
                sentiment_momentum=sentiment_momentum,
                sentiment_volatility=sentiment_volatility,
                news_volume=news_volume,
                social_volume=social_volume,
                sentiment_consensus=sentiment_consensus,
                market_sentiment=market_sentiment,
                sector_sentiment=sector_sentiment,
                confidence=confidence
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating sentiment factors for {symbol}: {e}")
            return self._create_default_sentiment_factor(symbol)
    
    def _calculate_weighted_sentiment(self, data: pd.DataFrame) -> float:
        """Calculate weighted sentiment score"""
        if data.empty:
            return 0.0
        
        # Weight by confidence and recency
        weights = []
        scores = []
        
        for _, row in data.iterrows():
            # Base weight from confidence
            weight = row.get('confidence', 0.5)
            
            # Adjust weight by recency (more recent = higher weight)
            hours_ago = (datetime.now() - row['timestamp']).total_seconds() / 3600
            recency_weight = np.exp(-hours_ago / 24)  # Exponential decay over 24 hours
            
            # Adjust weight by source
            source_weight = 1.0
            if row.get('source') == 'news':
                source_weight = 1.2  # News articles get higher weight
            elif row.get('source') in ['twitter', 'reddit']:
                source_weight = 0.8  # Social media gets lower weight
            
            final_weight = weight * recency_weight * source_weight
            weights.append(final_weight)
            scores.append(row['sentiment_score'])
        
        if sum(weights) == 0:
            return 0.0
        
        return np.average(scores, weights=weights)
    
    def _calculate_sentiment_momentum(self, data: pd.DataFrame, lookback_period: int) -> float:
        """Calculate sentiment momentum (change over time)"""
        if len(data) < 2:
            return 0.0
        
        # Get recent sentiment scores
        recent_data = data.tail(lookback_period)
        
        if len(recent_data) < 2:
            return 0.0
        
        # Calculate linear trend
        x = np.arange(len(recent_data))
        y = recent_data['sentiment_score'].values
        
        # Simple linear regression
        slope = np.polyfit(x, y, 1)[0]
        
        return slope
    
    def _calculate_sentiment_volatility(self, data: pd.DataFrame, lookback_period: int) -> float:
        """Calculate sentiment volatility"""
        if len(data) < 2:
            return 0.0
        
        recent_data = data.tail(lookback_period)
        
        if len(recent_data) < 2:
            return 0.0
        
        return recent_data['sentiment_score'].std()
    
    def _calculate_sentiment_consensus(self, data: pd.DataFrame) -> float:
        """Calculate sentiment consensus (agreement among sources)"""
        if data.empty:
            return 0.0
        
        # Calculate standard deviation of sentiment scores
        sentiment_std = data['sentiment_score'].std()
        
        # Convert to consensus score (lower std = higher consensus)
        consensus = 1.0 - min(sentiment_std, 1.0)
        
        return consensus
    
    def _calculate_market_relative_sentiment(self, symbol_data: pd.DataFrame, 
                                           all_data: pd.DataFrame) -> float:
        """Calculate sentiment relative to overall market"""
        if symbol_data.empty or all_data.empty:
            return 0.0
        
        # Calculate market average sentiment
        market_sentiment = all_data['sentiment_score'].mean()
        
        # Calculate symbol sentiment
        symbol_sentiment = symbol_data['sentiment_score'].mean()
        
        # Return relative sentiment
        return symbol_sentiment - market_sentiment
    
    def _calculate_sector_sentiment(self, symbol_data: pd.DataFrame, 
                                  all_data: pd.DataFrame) -> float:
        """Calculate sector sentiment (placeholder for sector classification)"""
        # This would require sector classification of symbols
        # For now, return a simple calculation
        if symbol_data.empty:
            return 0.0
        
        # Assume similar symbols are in the same sector
        # This is a simplified approach
        return symbol_data['sentiment_score'].mean()
    
    def _calculate_confidence(self, data: pd.DataFrame) -> float:
        """Calculate overall confidence in sentiment analysis"""
        if data.empty:
            return 0.0
        
        # Average confidence weighted by recency
        weights = []
        confidences = []
        
        for _, row in data.iterrows():
            hours_ago = (datetime.now() - row['timestamp']).total_seconds() / 3600
            recency_weight = np.exp(-hours_ago / 24)
            
            weights.append(recency_weight)
            confidences.append(row.get('confidence', 0.5))
        
        if sum(weights) == 0:
            return 0.0
        
        return np.average(confidences, weights=weights)
    
    def _create_default_sentiment_factor(self, symbol: str) -> SentimentFactor:
        """Create default sentiment factor when calculation fails"""
        return SentimentFactor(
            symbol=symbol,
            timestamp=datetime.now(),
            sentiment_score=0.0,
            sentiment_momentum=0.0,
            sentiment_volatility=0.0,
            news_volume=0,
            social_volume=0,
            sentiment_consensus=0.0,
            market_sentiment=0.0,
            sector_sentiment=0.0,
            confidence=0.0
        )
    
    def calculate_sentiment_factor_matrix(self, 
                                        sentiment_data: pd.DataFrame,
                                        symbols: List[str],
                                        lookback_period: int = 20) -> pd.DataFrame:
        """Calculate sentiment factors for multiple symbols"""
        factors = []
        
        for symbol in symbols:
            factor = self.calculate_sentiment_factors(sentiment_data, symbol, lookback_period)
            factors.append({
                'symbol': factor.symbol,
                'timestamp': factor.timestamp,
                'sentiment_score': factor.sentiment_score,
                'sentiment_momentum': factor.sentiment_momentum,
                'sentiment_volatility': factor.sentiment_volatility,
                'news_volume': factor.news_volume,
                'social_volume': factor.social_volume,
                'sentiment_consensus': factor.sentiment_consensus,
                'market_sentiment': factor.market_sentiment,
                'sector_sentiment': factor.sector_sentiment,
                'confidence': factor.confidence
            })
        
        return pd.DataFrame(factors)
    
    def create_sentiment_signal(self, sentiment_factor: SentimentFactor,
                               threshold: float = 0.1) -> Dict[str, Any]:
        """Create trading signal based on sentiment factor"""
        signal = {
            'symbol': sentiment_factor.symbol,
            'timestamp': sentiment_factor.timestamp,
            'signal': 'hold',
            'confidence': sentiment_factor.confidence,
            'reasoning': [],
            'strength': 0.0
        }
        
        # Signal logic based on sentiment score and momentum
        if sentiment_factor.sentiment_score > threshold and sentiment_factor.sentiment_momentum > 0:
            signal['signal'] = 'buy'
            signal['reasoning'].append(f"Positive sentiment ({sentiment_factor.sentiment_score:.3f})")
            signal['reasoning'].append(f"Positive momentum ({sentiment_factor.sentiment_momentum:.3f})")
            signal['strength'] = min(abs(sentiment_factor.sentiment_score) + abs(sentiment_factor.sentiment_momentum), 1.0)
            
        elif sentiment_factor.sentiment_score < -threshold and sentiment_factor.sentiment_momentum < 0:
            signal['signal'] = 'sell'
            signal['reasoning'].append(f"Negative sentiment ({sentiment_factor.sentiment_score:.3f})")
            signal['reasoning'].append(f"Negative momentum ({sentiment_factor.sentiment_momentum:.3f})")
            signal['strength'] = min(abs(sentiment_factor.sentiment_score) + abs(sentiment_factor.sentiment_momentum), 1.0)
        
        # Adjust confidence based on consensus and volume
        if sentiment_factor.sentiment_consensus > 0.7:
            signal['confidence'] *= 1.2
            signal['reasoning'].append(f"High consensus ({sentiment_factor.sentiment_consensus:.3f})")
        
        if sentiment_factor.news_volume + sentiment_factor.social_volume > 10:
            signal['confidence'] *= 1.1
            signal['reasoning'].append(f"High volume ({sentiment_factor.news_volume + sentiment_factor.social_volume} sources)")
        
        signal['confidence'] = min(signal['confidence'], 1.0)
        
        return signal 