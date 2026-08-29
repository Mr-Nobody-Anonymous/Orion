#!/usr/bin/env python3
"""
Complete LLM & NLP Extension Module Demo
Demonstrates the full pipeline: data collection → NLP processing → sentiment analysis → factor generation → strategy recommendation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_service.ai import (
    SentimentAnalyzer, NewsProcessor, SocialMediaMonitor, 
    LLMIntegration, NLPProcessor, SentimentFactorCalculator, LangChainAgent
)
from data_service.factors import FactorCalculator
from data_service.storage import DatabaseManager
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def create_sample_data():
    """Create sample data for demonstration"""
    # Sample news data
    news_data = [
        {
            'title': 'Apple Reports Strong Q4 Earnings, Stock Surges 5%',
            'content': 'Apple Inc. reported better-than-expected quarterly earnings, driven by strong iPhone sales and services growth.',
            'symbol': 'AAPL',
            'sentiment_score': 0.8,
            'source': 'news',
            'timestamp': datetime.now() - timedelta(hours=2)
        },
        {
            'title': 'Tesla Faces Production Challenges, Shares Decline',
            'content': 'Tesla Inc. announced production delays due to supply chain issues, causing investor concerns.',
            'symbol': 'TSLA',
            'sentiment_score': -0.6,
            'source': 'news',
            'timestamp': datetime.now() - timedelta(hours=4)
        },
        {
            'title': 'Google Announces New AI Breakthrough',
            'content': 'Google unveiled revolutionary AI technology that could transform the industry landscape.',
            'symbol': 'GOOGL',
            'sentiment_score': 0.9,
            'source': 'news',
            'timestamp': datetime.now() - timedelta(hours=1)
        }
    ]
    
    # Sample social media data
    social_data = [
        {
            'text': 'Just bought more $AAPL stock! Earnings look amazing! 🚀',
            'symbol': 'AAPL',
            'sentiment_score': 0.7,
            'source': 'twitter',
            'timestamp': datetime.now() - timedelta(minutes=30)
        },
        {
            'text': '$TSLA production issues are concerning. Might sell my position.',
            'symbol': 'TSLA',
            'sentiment_score': -0.5,
            'source': 'reddit',
            'timestamp': datetime.now() - timedelta(hours=1)
        },
        {
            'text': '$GOOGL AI announcement is game-changing! This is the future!',
            'symbol': 'GOOGL',
            'sentiment_score': 0.8,
            'source': 'twitter',
            'timestamp': datetime.now() - timedelta(minutes=45)
        }
    ]
    
    # Sample market data
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    symbols = ['AAPL', 'GOOGL', 'TSLA']
    
    market_data = {}
    for symbol in symbols:
        base_price = np.random.uniform(100, 500)
        returns = np.random.normal(0.001, 0.02, len(dates))
        prices = [base_price]
        
        for ret in returns[1:]:
            prices.append(prices[-1] * (1 + ret))
        
        market_data[symbol] = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
            'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, len(dates))
        }).set_index('date')
    
    return news_data, social_data, market_data

def demo_nlp_processing():
    """Demonstrate NLP processing pipeline"""
    print("\n=== NLP Processing Pipeline ===")
    
    # Initialize NLP processor
    nlp_processor = NLPProcessor()
    
    # Sample texts for processing
    sample_texts = [
        "Apple's quarterly earnings exceeded expectations, driving stock price higher.",
        "Tesla faces production delays due to supply chain issues.",
        "Google's new AI technology shows promising results for future growth."
    ]
    
    print("Processing sample texts...")
    processed_texts = []
    
    for text in sample_texts:
        processed = nlp_processor.preprocess_text(text)
        processed_texts.append(processed)
        
        print(f"\nOriginal: {text}")
        print(f"Cleaned: {processed.cleaned_text}")
        print(f"Sentiment: {processed.sentiment_label} ({processed.sentiment_score:.3f})")
        print(f"Keywords: {processed.keywords[:5]}")
        print(f"Topics: {processed.topics}")
    
    # Batch sentiment analysis
    print("\n--- Batch Sentiment Analysis ---")
    sentiment_results = nlp_processor.analyze_sentiment_batch(sample_texts)
    
    for i, result in enumerate(sentiment_results):
        print(f"Text {i+1}: {result.sentiment_label} ({result.sentiment_score:.3f})")
    
    # Calculate market sentiment
    market_sentiment = nlp_processor.calculate_market_sentiment(sentiment_results)
    print(f"\nOverall Market Sentiment: {market_sentiment['sentiment_label']} ({market_sentiment['overall_sentiment']:.3f})")
    print(f"Top Keywords: {market_sentiment['top_keywords']}")
    print(f"Top Topics: {market_sentiment['top_topics']}")

def demo_sentiment_factor_generation():
    """Demonstrate sentiment factor generation"""
    print("\n=== Sentiment Factor Generation ===")
    
    # Create sample sentiment data
    sentiment_data = []
    symbols = ['AAPL', 'GOOGL', 'TSLA']
    
    for symbol in symbols:
        for i in range(20):  # 20 sentiment data points per symbol
            sentiment_data.append({
                'symbol': symbol,
                'sentiment_score': np.random.normal(0.1, 0.3),
                'confidence': np.random.uniform(0.6, 0.9),
                'source': np.random.choice(['news', 'twitter', 'reddit']),
                'timestamp': datetime.now() - timedelta(hours=i)
            })
    
    sentiment_df = pd.DataFrame(sentiment_data)
    
    # Initialize sentiment factor calculator
    factor_calculator = SentimentFactorCalculator()
    
    print("Calculating sentiment factors...")
    
    for symbol in symbols:
        factor = factor_calculator.calculate_sentiment_factors(sentiment_df, symbol)
        
        print(f"\n{symbol} Sentiment Factors:")
        print(f"  Sentiment Score: {factor.sentiment_score:.3f}")
        print(f"  Sentiment Momentum: {factor.sentiment_momentum:.3f}")
        print(f"  Sentiment Volatility: {factor.sentiment_volatility:.3f}")
        print(f"  News Volume: {factor.news_volume}")
        print(f"  Social Volume: {factor.social_volume}")
        print(f"  Sentiment Consensus: {factor.sentiment_consensus:.3f}")
        print(f"  Confidence: {factor.confidence:.3f}")
        
        # Generate trading signal
        signal = factor_calculator.create_sentiment_signal(factor)
        print(f"  Trading Signal: {signal['signal']} (confidence: {signal['confidence']:.3f})")
        print(f"  Reasoning: {'; '.join(signal['reasoning'][:2])}")
    
    # Calculate factor matrix
    print("\n--- Sentiment Factor Matrix ---")
    factor_matrix = factor_calculator.calculate_sentiment_factor_matrix(sentiment_df, symbols)
    print(factor_matrix[['symbol', 'sentiment_score', 'sentiment_momentum', 'confidence']].round(3))

def demo_llm_integration():
    """Demonstrate LLM integration"""
    print("\n=== LLM Integration ===")
    
    # Initialize LLM integration (using mock provider for demo)
    try:
        llm_integration = LLMIntegration(provider="openai", api_key="demo-key")
        print("LLM Integration initialized successfully")
        
        # Mock market data
        market_data = pd.DataFrame({
            'AAPL_return': [0.01, -0.02, 0.03, 0.01, -0.01],
            'GOOGL_return': [0.02, -0.01, 0.04, -0.02, 0.01],
            'volume': [1000000, 1200000, 900000, 1100000, 1300000]
        })
        
        # Mock factor data
        factor_data = pd.DataFrame({
            'momentum_20d': [0.05, -0.03, 0.08, 0.02, -0.01],
            'pe_ratio': [25.5, 30.2, 22.1, 28.3, 26.7],
            'roe': [0.15, 0.12, 0.18, 0.14, 0.16]
        })
        
        print("LLM features available:")
        print("- Market data analysis")
        print("- Trading signal generation")
        print("- Risk assessment")
        print("- Portfolio optimization")
        print("- Trading Q&A")
        
    except Exception as e:
        print(f"LLM Integration demo (mock): {e}")
        print("Note: Requires valid API keys for full functionality")

def demo_langchain_agent():
    """Demonstrate LangChain agent"""
    print("\n=== LangChain Agent ===")
    
    try:
        # Initialize components
        llm_integration = LLMIntegration(provider="openai", api_key="demo-key")
        nlp_processor = NLPProcessor()
        
        # Initialize LangChain agent
        agent = LangChainAgent(llm_integration, nlp_processor)
        print("LangChain Agent initialized successfully")
        
        # Mock data
        news_data, social_data, market_data = create_sample_data()
        
        # Create sample market data DataFrame
        market_df = pd.DataFrame({
            'close': [150, 148, 152, 151, 149],
            'volume': [1000000, 1200000, 900000, 1100000, 1300000]
        })
        
        # Mock sentiment data
        sentiment_df = pd.DataFrame([
            {'symbol': 'AAPL', 'sentiment_score': 0.8, 'confidence': 0.9, 'source': 'news'},
            {'symbol': 'GOOGL', 'sentiment_score': 0.9, 'confidence': 0.8, 'source': 'news'},
            {'symbol': 'TSLA', 'sentiment_score': -0.6, 'confidence': 0.7, 'source': 'news'}
        ])
        
        # Mock portfolio data
        portfolio_data = {
            'total_value': 1000000,
            'cash': 200000,
            'num_positions': 3,
            'risk_level': 'medium'
        }
        
        symbols = ['AAPL', 'GOOGL', 'TSLA']
        
        print("LangChain Agent features available:")
        print("- Strategy recommendation generation")
        print("- Market intelligence analysis")
        print("- Automated report generation")
        print("- Multi-tool integration")
        
        # Note: Actual LLM calls would require valid API keys
        print("\nNote: Actual LLM calls require valid API keys")
        
    except Exception as e:
        print(f"LangChain Agent demo (mock): {e}")

def demo_complete_pipeline():
    """Demonstrate complete LLM & NLP pipeline"""
    print("\n=== Complete LLM & NLP Pipeline ===")
    
    # Step 1: Data Collection
    print("1. Data Collection")
    news_data, social_data, market_data = create_sample_data()
    print(f"   - Collected {len(news_data)} news articles")
    print(f"   - Collected {len(social_data)} social media posts")
    print(f"   - Market data for {len(market_data)} symbols")
    
    # Step 2: NLP Processing
    print("\n2. NLP Processing")
    nlp_processor = NLPProcessor()
    
    # Process news and social media texts
    all_texts = [item['title'] + ' ' + item['content'] for item in news_data]
    all_texts.extend([item['text'] for item in social_data])
    
    processed_texts = []
    for text in all_texts[:5]:  # Process first 5 for demo
        processed = nlp_processor.preprocess_text(text)
        processed_texts.append(processed)
    
    print(f"   - Processed {len(processed_texts)} texts")
    print(f"   - Average sentiment: {np.mean([p.sentiment_score for p in processed_texts]):.3f}")
    
    # Step 3: Sentiment Factor Generation
    print("\n3. Sentiment Factor Generation")
    factor_calculator = SentimentFactorCalculator()
    
    # Create sentiment data
    sentiment_data = []
    for item in news_data + social_data:
        sentiment_data.append({
            'symbol': item['symbol'],
            'sentiment_score': item['sentiment_score'],
            'confidence': np.random.uniform(0.7, 0.9),
            'source': item['source'],
            'timestamp': item['timestamp']
        })
    
    sentiment_df = pd.DataFrame(sentiment_data)
    symbols = ['AAPL', 'GOOGL', 'TSLA']
    
    factors = []
    for symbol in symbols:
        factor = factor_calculator.calculate_sentiment_factors(sentiment_df, symbol)
        factors.append(factor)
        print(f"   - {symbol}: sentiment={factor.sentiment_score:.3f}, momentum={factor.sentiment_momentum:.3f}")
    
    # Step 4: Factor Integration
    print("\n4. Factor Integration")
    print("   - Sentiment factors can be integrated with technical factors")
    print("   - Combined factors can be used in strategy generation")
    print("   - Multi-factor models can be backtested")
    
    # Step 5: Strategy Generation
    print("\n5. Strategy Generation")
    print("   - LLM can generate trading strategies based on sentiment analysis")
    print("   - LangChain agent can provide intelligent recommendations")
    print("   - Automated reports can be generated")
    
    # Step 6: Risk Management
    print("\n6. Risk Management")
    print("   - Sentiment volatility can be used for risk assessment")
    print("   - Consensus metrics can indicate market stability")
    print("   - Real-time sentiment monitoring can trigger alerts")
    
    print("\nPipeline completed successfully!")

def main():
    """Main demonstration function"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting Complete LLM & NLP Extension Module Demo")
    
    try:
        # Run demonstrations
        demo_nlp_processing()
        demo_sentiment_factor_generation()
        demo_llm_integration()
        demo_langchain_agent()
        demo_complete_pipeline()
        
        logger.info("All demonstrations completed successfully")
        
        print("\n" + "="*60)
        print("LLM & NLP Extension Module Features:")
        print("="*60)
        print("✅ NLP Processing:")
        print("   - Text preprocessing and cleaning")
        print("   - Sentiment analysis (multiple models)")
        print("   - Keyword extraction and topic modeling")
        print("   - Language detection")
        print("   - Financial entity extraction")
        
        print("\n✅ Sentiment Factor Generation:")
        print("   - Sentiment score calculation")
        print("   - Sentiment momentum and volatility")
        print("   - News and social media volume analysis")
        print("   - Sentiment consensus measurement")
        print("   - Trading signal generation")
        
        print("\n✅ LLM Integration:")
        print("   - Multiple LLM provider support")
        print("   - Market data analysis")
        print("   - Trading signal generation")
        print("   - Risk assessment")
        print("   - Portfolio optimization")
        print("   - Trading Q&A")
        
        print("\n✅ LangChain Agent:")
        print("   - Intelligent strategy recommendation")
        print("   - Market intelligence analysis")
        print("   - Automated report generation")
        print("   - Multi-tool integration")
        print("   - Chain-of-thought reasoning")
        
        print("\n✅ Complete Pipeline:")
        print("   - Data collection → NLP processing → Factor generation")
        print("   - Sentiment analysis → Strategy recommendation")
        print("   - Risk management → Automated reporting")
        
        print("\n" + "="*60)
        print("Next Steps:")
        print("="*60)
        print("1. Install required dependencies:")
        print("   pip install -e .[ai]")
        print("   pip install langchain langchain-openai langchain-community")
        print("   pip install spacy transformers nltk")
        print("   python -m spacy download en_core_web_sm")
        
        print("\n2. Set up API keys:")
        print("   export OPENAI_API_KEY='your-api-key'")
        
        print("\n3. Run with real data:")
        print("   python examples/llm_nlp_complete_demo.py")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"\nError: {e}")
        print("\nNote: This demo uses mock data. For full functionality, set up API keys and install dependencies.")

if __name__ == "__main__":
    main() 