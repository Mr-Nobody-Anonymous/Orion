#!/usr/bin/env python3
"""
LangChain + LLM Integration Demo for Trading System
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_service.ai import LLMIntegration
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
    """Create sample market and factor data"""
    # Sample price data
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN']
    
    price_data = {}
    for symbol in symbols:
        # Generate realistic price data
        base_price = np.random.uniform(100, 500)
        returns = np.random.normal(0.001, 0.02, len(dates))
        prices = [base_price]
        
        for ret in returns[1:]:
            prices.append(prices[-1] * (1 + ret))
        
        price_data[symbol] = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
            'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, len(dates))
        })
    
    # Sample factor data
    factor_data = {}
    for symbol in symbols:
        factor_data[symbol] = pd.DataFrame({
            'momentum_20d': np.random.uniform(-0.2, 0.2, len(dates)),
            'pe_ratio': np.random.uniform(10, 50, len(dates)),
            'roe': np.random.uniform(0.05, 0.25, len(dates)),
            'volatility': np.random.uniform(0.1, 0.4, len(dates)),
            'market_cap': np.random.uniform(1e9, 1e12, len(dates))
        }, index=dates)
    
    return price_data, factor_data

def demo_market_analysis(llm_integration, price_data, symbols):
    """Demonstrate market analysis using LLM"""
    print("\n=== Market Analysis Demo ===")
    
    # Create market data summary
    market_data = pd.DataFrame()
    for symbol in symbols:
        symbol_data = price_data[symbol]
        market_data[f'{symbol}_return'] = symbol_data['close'].pct_change()
        market_data[f'{symbol}_volume'] = symbol_data['volume']
    
    # Analyze market data
    insight = llm_integration.analyze_market_data(market_data, symbols)
    
    print(f"Insight Type: {insight.insight_type}")
    print(f"Confidence: {insight.confidence}")
    print(f"Symbols: {insight.symbols}")
    print(f"Content: {insight.content[:200]}...")
    print(f"Reasoning: {insight.reasoning[:200]}...")

def demo_signal_generation(llm_integration, factor_data, price_data, symbols):
    """Demonstrate trading signal generation using LLM"""
    print("\n=== Trading Signal Generation Demo ===")
    
    # Use last period data for signal generation
    latest_factors = pd.DataFrame()
    latest_prices = pd.DataFrame()
    
    for symbol in symbols:
        latest_factors[symbol] = factor_data[symbol].iloc[-1]
        latest_prices[symbol] = price_data[symbol].iloc[-1]
    
    # Generate trading signals
    strategy_context = "Multi-factor momentum strategy with value tilt"
    insight = llm_integration.generate_trading_signals(
        latest_factors, latest_prices, strategy_context
    )
    
    print(f"Insight Type: {insight.insight_type}")
    print(f"Strategy Context: {strategy_context}")
    print(f"Content: {insight.content[:300]}...")
    print(f"Reasoning: {insight.reasoning[:200]}...")

def demo_risk_assessment(llm_integration):
    """Demonstrate risk assessment using LLM"""
    print("\n=== Risk Assessment Demo ===")
    
    # Sample portfolio data
    portfolio_data = {
        'total_value': 1000000,
        'positions': {
            'AAPL': {'quantity': 100, 'avg_price': 150, 'current_price': 155},
            'GOOGL': {'quantity': 50, 'avg_price': 2800, 'current_price': 2750},
            'TSLA': {'quantity': 200, 'avg_price': 200, 'current_price': 180}
        },
        'cash': 200000,
        'leverage': 1.2,
        'daily_pnl': -5000
    }
    
    # Sample market conditions
    market_conditions = {
        'volatility_index': 25.5,
        'market_trend': 'bearish',
        'sector_performance': {
            'technology': -0.05,
            'consumer_discretionary': -0.03,
            'healthcare': 0.02
        },
        'risk_factors': ['inflation_concerns', 'fed_policy_uncertainty']
    }
    
    # Assess risk
    insight = llm_integration.assess_risk(portfolio_data, market_conditions)
    
    print(f"Insight Type: {insight.insight_type}")
    print(f"Portfolio Value: ${portfolio_data['total_value']:,}")
    print(f"Daily P&L: ${portfolio_data['daily_pnl']:,}")
    print(f"Content: {insight.content[:300]}...")
    print(f"Reasoning: {insight.reasoning[:200]}...")

def demo_portfolio_optimization(llm_integration, factor_data, symbols):
    """Demonstrate portfolio optimization using LLM"""
    print("\n=== Portfolio Optimization Demo ===")
    
    # Current portfolio weights
    current_weights = {
        'AAPL': 0.3,
        'GOOGL': 0.25,
        'MSFT': 0.2,
        'TSLA': 0.15,
        'AMZN': 0.1
    }
    
    # Factor scores for each stock
    factor_scores = {}
    for symbol in symbols:
        latest_factors = factor_data[symbol].iloc[-1]
        factor_scores[symbol] = {
            'momentum': float(latest_factors['momentum_20d']),
            'value': 1.0 / float(latest_factors['pe_ratio']),  # Inverse P/E
            'quality': float(latest_factors['roe']),
            'risk': 1.0 / float(latest_factors['volatility'])  # Inverse volatility
        }
    
    # Optimization constraints
    constraints = {
        'min_weight': 0.05,
        'max_weight': 0.4,
        'target_return': 0.12,
        'max_volatility': 0.2,
        'sector_limits': {
            'technology': 0.6,
            'consumer_discretionary': 0.3
        }
    }
    
    # Optimize portfolio
    insight = llm_integration.optimize_portfolio(
        current_weights, factor_scores, constraints
    )
    
    print(f"Insight Type: {insight.insight_type}")
    print(f"Current Weights: {current_weights}")
    print(f"Constraints: {constraints}")
    print(f"Content: {insight.content[:300]}...")
    print(f"Reasoning: {insight.reasoning[:200]}...")

def demo_question_answering(llm_integration):
    """Demonstrate trading question answering using LLM"""
    print("\n=== Trading Q&A Demo ===")
    
    questions = [
        "What are the key factors to consider when implementing a momentum trading strategy?",
        "How should I adjust my portfolio during high market volatility?",
        "What are the risks of over-diversification in a trading portfolio?",
        "How do I calculate the optimal position size for a trade?"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"\nQuestion {i}: {question}")
        
        # Add context data for some questions
        context_data = None
        if "volatility" in question.lower():
            context_data = {
                'current_vix': 25.5,
                'market_conditions': 'bearish',
                'portfolio_beta': 1.1
            }
        
        response = llm_integration.answer_trading_question(question, context_data)
        
        print(f"Answer: {response.content[:200]}...")
        print(f"Confidence: {response.confidence}")
        print(f"Model: {response.model_used}")
        print(f"Tokens Used: {response.tokens_used}")

def demo_provider_info(llm_integration):
    """Demonstrate provider information and usage stats"""
    print("\n=== Provider Information Demo ===")
    
    provider_info = llm_integration.get_provider_info()
    usage_stats = llm_integration.get_usage_stats()
    
    print(f"Provider: {provider_info['provider']}")
    print(f"Model: {provider_info['model']}")
    print(f"Max Tokens: {provider_info['max_tokens']}")
    print(f"Supports Functions: {provider_info['supports_functions']}")
    print(f"Usage Stats: {usage_stats}")

def main():
    """Main demonstration function"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting LangChain + LLM Integration Demo")
    
    try:
        # Initialize LLM integration
        # Note: For demo purposes, we'll use a mock provider
        # In production, you would provide actual API keys
        llm_integration = LLMIntegration(
            provider="openai",  # or "local" for local models
            api_key="your-api-key-here",  # Replace with actual key
            model="gpt-3.5-turbo"
        )
        
        logger.info("LLM Integration initialized successfully")
        
        # Create sample data
        price_data, factor_data = create_sample_data()
        symbols = list(price_data.keys())
        
        logger.info(f"Created sample data for {len(symbols)} symbols")
        
        # Run demonstrations
        demo_provider_info(llm_integration)
        demo_market_analysis(llm_integration, price_data, symbols)
        demo_signal_generation(llm_integration, factor_data, price_data, symbols)
        demo_risk_assessment(llm_integration)
        demo_portfolio_optimization(llm_integration, factor_data, symbols)
        demo_question_answering(llm_integration)
        
        logger.info("All demonstrations completed successfully")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"\nError: {e}")
        print("\nNote: This demo requires valid API keys for OpenAI or local model setup.")
        print("To run with OpenAI:")
        print("1. Get an API key from https://platform.openai.com/")
        print("2. Set OPENAI_API_KEY environment variable")
        print("3. Update the api_key parameter in the code")
        print("\nTo run with local models:")
        print("1. Install transformers: pip install transformers torch")
        print("2. Set provider='local' in LLMIntegration initialization")

if __name__ == "__main__":
    main() 