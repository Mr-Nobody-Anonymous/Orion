#!/usr/bin/env python3
"""
Example script demonstrating LLM market sentiment analysis
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_service.ai import SentimentAnalyzer, NewsProcessor, SocialMediaMonitor
from data_service.storage import DatabaseManager, FileStorage
from data_service.vector_db import VectorStore
from data_service.api import APIManager
import pandas as pd
from datetime import datetime, timedelta
import logging

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main():
    """Main function demonstrating AI sentiment analysis"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting AI sentiment analysis demonstration")
    
    # Initialize components
    try:
        # Initialize storage
        db_manager = DatabaseManager()
        file_storage = FileStorage()
        
        # Initialize AI components
        sentiment_analyzer = SentimentAnalyzer()
        news_processor = NewsProcessor()
        social_monitor = SocialMediaMonitor()
        
        # Initialize vector store
        vector_store = VectorStore()
        
        # Initialize API manager
        api_manager = APIManager()
        
        logger.info("All components initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing components: {e}")
        return
    
    # Example 1: News sentiment analysis
    logger.info("=== Example 1: News Sentiment Analysis ===")
    
    # Fetch news for BTC
    symbols = ['BTC', 'ETH', 'AAPL']
    news_items = news_processor.fetch_all_news(symbols, days_back=7)
    
    if news_items:
        logger.info(f"Fetched {len(news_items)} news items")
        
        # Analyze sentiment for each news item
        sentiment_results = []
        for news_item in news_items[:5]:  # Analyze first 5 items
            sentiment = sentiment_analyzer.analyze_text_sentiment(
                news_item.title + " " + news_item.content,
                news_item.symbol
            )
            sentiment_results.append(sentiment)
            
            logger.info(f"News: {news_item.title[:50]}...")
            logger.info(f"Sentiment: {sentiment.sentiment_score:.3f} (confidence: {sentiment.confidence:.3f})")
        
        # Calculate market sentiment
        market_sentiment = sentiment_analyzer.calculate_market_sentiment(sentiment_results)
        logger.info(f"Market sentiment: {market_sentiment}")
        
        # Generate trading signal
        signal = sentiment_analyzer.generate_sentiment_signal(market_sentiment)
        logger.info(f"Trading signal: {signal}")
        
        # Save results
        file_storage.save_news_to_file(news_items, "data/news_btc_eth_aapl.json")
        
    else:
        logger.warning("No news items fetched")
    
    # Example 2: Social media sentiment analysis
    logger.info("\n=== Example 2: Social Media Sentiment Analysis ===")
    
    # Fetch social media posts
    social_posts = social_monitor.fetch_all_social_posts(symbols)
    
    if social_posts:
        logger.info(f"Fetched {len(social_posts)} social media posts")
        
        # Filter by engagement
        high_engagement_posts = social_monitor.filter_posts_by_engagement(social_posts, min_engagement=5)
        logger.info(f"High engagement posts: {len(high_engagement_posts)}")
        
        # Calculate social metrics
        social_metrics = social_monitor.calculate_social_metrics(social_posts)
        logger.info(f"Social metrics: {social_metrics}")
        
        # Save posts
        social_monitor.save_posts_to_file(social_posts, "data/social_posts.json")
        
    else:
        logger.warning("No social media posts fetched")
    
    # Example 3: Vector database for document search
    logger.info("\n=== Example 3: Vector Database Document Search ===")
    
    # Create sample documents
    sample_documents = [
        {
            'id': 'doc1',
            'content': 'Bitcoin price reaches new all-time high as institutional adoption increases',
            'metadata': {'symbol': 'BTC', 'type': 'news'},
            'source': 'news_api'
        },
        {
            'id': 'doc2', 
            'content': 'Ethereum network upgrade improves transaction speed and reduces fees',
            'metadata': {'symbol': 'ETH', 'type': 'news'},
            'source': 'news_api'
        },
        {
            'id': 'doc3',
            'content': 'Apple reports strong quarterly earnings with iPhone sales growth',
            'metadata': {'symbol': 'AAPL', 'type': 'earnings'},
            'source': 'financial_news'
        }
    ]
    
    # Add documents to vector store (simplified - would need embeddings)
    logger.info("Vector database functionality demonstrated (embeddings would be generated)")
    
    # Example 4: API management
    logger.info("\n=== Example 4: API Management ===")
    
    # Register sample API endpoints
    from data_service.api.api_manager import APIEndpoint
    
    # Example: Alpha Vantage API
    alpha_vantage_endpoint = APIEndpoint(
        name='alpha_vantage_news',
        url='https://www.alphavantage.co/query',
        method='GET',
        headers={},
        params={'function': 'NEWS_SENTIMENT', 'apikey': 'demo'},
        rate_limit=5  # 5 requests per minute
    )
    
    api_manager.register_endpoint('alpha_vantage_news', alpha_vantage_endpoint)
    logger.info("API endpoint registered: alpha_vantage_news")
    
    # Get performance metrics
    metrics = api_manager.get_performance_metrics()
    logger.info(f"API performance metrics: {metrics}")
    
    # Example 5: Save sentiment data to database
    logger.info("\n=== Example 5: Data Persistence ===")
    
    # Save sentiment data to database
    for sentiment in sentiment_results:
        sentiment_data = {
            'strategy_name': 'sentiment_analysis',
            'symbol': sentiment.symbol,
            'signal_type': 'sentiment_score',
            'strength': sentiment.sentiment_score,
            'timestamp': sentiment.timestamp
        }
        db_manager.save_signal(sentiment_data)
    
    logger.info("Sentiment data saved to database")
    
    # Generate performance report
    performance_data = {
        'date': datetime.now().date(),
        'total_pnl': 0.0,  # Would be calculated from actual trading
        'daily_return': 0.0,
        'max_drawdown': 0.0,
        'sharpe_ratio': 0.0,
        'win_rate': 0.0,
        'total_trades': 0
    }
    
    file_storage.save_performance_report(performance_data, "sentiment_analysis")
    logger.info("Performance report saved")
    
    # Cleanup
    db_manager.close()
    vector_store.close()
    
    logger.info("AI sentiment analysis demonstration completed")

if __name__ == "__main__":
    main() 