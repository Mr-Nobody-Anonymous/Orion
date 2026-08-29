import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta
import requests
import json
from dataclasses import dataclass

@dataclass
class SentimentData:
    """Sentiment analysis result data structure"""
    timestamp: datetime
    symbol: str
    sentiment_score: float  # -1 to 1 (negative to positive)
    confidence: float
    source: str
    text: str
    keywords: List[str]

class SentimentAnalyzer:
    """Market sentiment analyzer using LLM and traditional NLP"""
    
    def __init__(self, openai_api_key: Optional[str] = None, 
                 use_openai: bool = True):
        self.openai_api_key = openai_api_key
        self.use_openai = use_openai
        self.logger = logging.getLogger(__name__)
        
        # Initialize sentiment models
        self._init_models()
        
    def _init_models(self):
        """Initialize sentiment analysis models"""
        try:
            # Try to use OpenAI if available
            if self.use_openai and self.openai_api_key:
                import openai
                openai.api_key = self.openai_api_key
                self.openai_client = openai
                self.logger.info("OpenAI client initialized")
            else:
                self.openai_client = None
                self.logger.info("Using local sentiment models")
                
            # Initialize local sentiment models as fallback
            self._init_local_models()
            
        except Exception as e:
            self.logger.error(f"Error initializing sentiment models: {e}")
            self._init_local_models()
    
    def _init_local_models(self):
        """Initialize local sentiment analysis models"""
        try:
            from textblob import TextBlob
            self.textblob = TextBlob
            
            # Try to load more advanced local models
            try:
                from transformers import pipeline
                self.sentiment_pipeline = pipeline("sentiment-analysis", 
                                                 model="cardiffnlp/twitter-roberta-base-sentiment")
                self.logger.info("Local sentiment pipeline initialized")
            except ImportError:
                self.sentiment_pipeline = None
                self.logger.warning("Transformers not available, using TextBlob only")
                
        except ImportError:
            self.logger.error("TextBlob not available for sentiment analysis")
            self.textblob = None
            self.sentiment_pipeline = None
    
    def analyze_text_sentiment(self, text: str, symbol: str = None) -> SentimentData:
        """Analyze sentiment of given text"""
        try:
            # Try OpenAI first if available
            if self.openai_client:
                return self._analyze_with_openai(text, symbol)
            else:
                return self._analyze_with_local_models(text, symbol)
                
        except Exception as e:
            self.logger.error(f"Error analyzing sentiment: {e}")
            return self._create_default_sentiment(text, symbol)
    
    def _analyze_with_openai(self, text: str, symbol: str) -> SentimentData:
        """Analyze sentiment using OpenAI GPT"""
        try:
            prompt = f"""
            Analyze the sentiment of the following financial news text for {symbol if symbol else 'the market'}.
            Consider market impact, investor sentiment, and potential price movement.
            
            Text: {text}
            
            Provide a JSON response with:
            - sentiment_score: float between -1 (very negative) and 1 (very positive)
            - confidence: float between 0 and 1
            - keywords: list of important financial keywords
            - market_impact: brief analysis of potential market impact
            """
            
            response = self.openai_client.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial sentiment analyst. Provide accurate, objective sentiment analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return SentimentData(
                timestamp=datetime.now(),
                symbol=symbol or "GENERAL",
                sentiment_score=result.get('sentiment_score', 0.0),
                confidence=result.get('confidence', 0.5),
                source="OpenAI GPT",
                text=text,
                keywords=result.get('keywords', [])
            )
            
        except Exception as e:
            self.logger.error(f"OpenAI sentiment analysis failed: {e}")
            return self._analyze_with_local_models(text, symbol)
    
    def _analyze_with_local_models(self, text: str, symbol: str) -> SentimentData:
        """Analyze sentiment using local models"""
        sentiment_score = 0.0
        confidence = 0.5
        keywords = []
        
        # Use TextBlob for basic sentiment
        if self.textblob:
            blob = self.textblob(text)
            sentiment_score = blob.sentiment.polarity
            confidence = abs(blob.sentiment.subjectivity)
            
            # Extract keywords (simple approach)
            keywords = [word.lower() for word in blob.words 
                       if len(word) > 3 and word.isalpha()]
        
        # Use transformers pipeline if available
        if self.sentiment_pipeline:
            try:
                result = self.sentiment_pipeline(text)[0]
                # Map label to score
                label_to_score = {'LABEL_0': -1, 'LABEL_1': 0, 'LABEL_2': 1}
                pipeline_score = label_to_score.get(result['label'], 0)
                
                # Combine scores
                sentiment_score = (sentiment_score + pipeline_score) / 2
                confidence = max(confidence, result['score'])
                
            except Exception as e:
                self.logger.warning(f"Pipeline sentiment analysis failed: {e}")
        
        return SentimentData(
            timestamp=datetime.now(),
            symbol=symbol or "GENERAL",
            sentiment_score=sentiment_score,
            confidence=confidence,
            source="Local Models",
            text=text,
            keywords=keywords[:10]  # Limit to top 10 keywords
        )
    
    def _create_default_sentiment(self, text: str, symbol: str) -> SentimentData:
        """Create default sentiment data when analysis fails"""
        return SentimentData(
            timestamp=datetime.now(),
            symbol=symbol or "GENERAL",
            sentiment_score=0.0,
            confidence=0.0,
            source="Default",
            text=text,
            keywords=[]
        )
    
    def analyze_news_batch(self, news_items: List[Dict[str, Any]]) -> List[SentimentData]:
        """Analyze sentiment for a batch of news items"""
        results = []
        
        for news_item in news_items:
            try:
                text = news_item.get('title', '') + ' ' + news_item.get('content', '')
                symbol = news_item.get('symbol')
                
                sentiment = self.analyze_text_sentiment(text, symbol)
                results.append(sentiment)
                
            except Exception as e:
                self.logger.error(f"Error analyzing news item: {e}")
                continue
        
        return results
    
    def calculate_market_sentiment(self, sentiment_data: List[SentimentData], 
                                 symbol: str = None) -> Dict[str, float]:
        """Calculate aggregate market sentiment metrics"""
        if not sentiment_data:
            return {}
        
        # Filter by symbol if specified
        if symbol:
            sentiment_data = [s for s in sentiment_data if s.symbol == symbol]
        
        if not sentiment_data:
            return {}
        
        # Calculate weighted average sentiment
        total_weight = sum(s.confidence for s in sentiment_data)
        if total_weight == 0:
            return {}
        
        weighted_sentiment = sum(s.sentiment_score * s.confidence for s in sentiment_data) / total_weight
        
        # Calculate sentiment volatility
        sentiment_scores = [s.sentiment_score for s in sentiment_data]
        sentiment_volatility = np.std(sentiment_scores)
        
        # Calculate sentiment momentum (change over time)
        sorted_data = sorted(sentiment_data, key=lambda x: x.timestamp)
        if len(sorted_data) >= 2:
            recent_sentiment = np.mean([s.sentiment_score for s in sorted_data[-5:]])  # Last 5 items
            older_sentiment = np.mean([s.sentiment_score for s in sorted_data[:-5]]) if len(sorted_data) > 5 else recent_sentiment
            sentiment_momentum = recent_sentiment - older_sentiment
        else:
            sentiment_momentum = 0.0
        
        return {
            'weighted_sentiment': weighted_sentiment,
            'sentiment_volatility': sentiment_volatility,
            'sentiment_momentum': sentiment_momentum,
            'confidence': np.mean([s.confidence for s in sentiment_data]),
            'sample_size': len(sentiment_data)
        }
    
    def generate_sentiment_signal(self, sentiment_metrics: Dict[str, float]) -> Dict[str, Any]:
        """Generate trading signal based on sentiment analysis"""
        if not sentiment_metrics:
            return {}
        
        sentiment = sentiment_metrics.get('weighted_sentiment', 0)
        momentum = sentiment_metrics.get('sentiment_momentum', 0)
        volatility = sentiment_metrics.get('sentiment_volatility', 0)
        confidence = sentiment_metrics.get('confidence', 0)
        
        # Define signal thresholds
        strong_bullish = sentiment > 0.3 and momentum > 0.1 and confidence > 0.7
        bullish = sentiment > 0.1 and momentum > 0.05 and confidence > 0.5
        strong_bearish = sentiment < -0.3 and momentum < -0.1 and confidence > 0.7
        bearish = sentiment < -0.1 and momentum < -0.05 and confidence > 0.5
        
        signal_strength = 0.0
        signal_direction = 'neutral'
        
        if strong_bullish:
            signal_direction = 'strong_buy'
            signal_strength = min(abs(sentiment) + abs(momentum), 1.0)
        elif bullish:
            signal_direction = 'buy'
            signal_strength = min(abs(sentiment) + abs(momentum), 0.7)
        elif strong_bearish:
            signal_direction = 'strong_sell'
            signal_strength = min(abs(sentiment) + abs(momentum), 1.0)
        elif bearish:
            signal_direction = 'sell'
            signal_strength = min(abs(sentiment) + abs(momentum), 0.7)
        
        return {
            'signal_direction': signal_direction,
            'signal_strength': signal_strength,
            'sentiment_score': sentiment,
            'momentum': momentum,
            'confidence': confidence,
            'timestamp': datetime.now()
        } 