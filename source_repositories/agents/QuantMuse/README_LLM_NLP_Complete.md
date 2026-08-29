# LLM & NLP Extension Module - Complete Implementation

This document describes the complete LLM & NLP extension module for the trading system, including all components from data collection to strategy generation.

## Overview

The LLM & NLP extension module provides a comprehensive pipeline for:

1. **Data Collection**: News and social media data gathering
2. **NLP Processing**: Text preprocessing, sentiment analysis, topic modeling
3. **Sentiment Factor Generation**: Converting sentiment data into quantitative factors
4. **LLM Integration**: Intelligent analysis and strategy generation
5. **LangChain Agent**: Automated trading recommendations and reports

## Architecture

```
Data Sources → NLP Processing → Sentiment Analysis → Factor Generation → Strategy Engine
     ↓              ↓                ↓                ↓                ↓
News APIs    Text Cleaning    Sentiment Scores   Sentiment Factors  Trading Signals
Social APIs  Tokenization     Topic Modeling     Momentum/Variance  Risk Assessment
RSS Feeds    Entity Extraction Keyword Extraction Consensus Metrics  Portfolio Optimization
```

## Components

### 1. NLPProcessor (`data_service/ai/nlp_processor.py`)

**Features:**
- Text preprocessing and cleaning
- Tokenization (spaCy, NLTK)
- Sentiment analysis (multiple models)
- Keyword extraction
- Topic modeling
- Language detection
- Financial entity extraction

**Usage:**
```python
from data_service.ai import NLPProcessor

nlp = NLPProcessor()

# Process single text
processed = nlp.preprocess_text("Apple's earnings exceeded expectations")
print(f"Sentiment: {processed.sentiment_label} ({processed.sentiment_score:.3f})")

# Batch processing
texts = ["Text 1", "Text 2", "Text 3"]
results = nlp.analyze_sentiment_batch(texts)

# Market sentiment
market_sentiment = nlp.calculate_market_sentiment(results)
```

### 2. SentimentFactorCalculator (`data_service/ai/sentiment_factor.py`)

**Features:**
- Sentiment score calculation (weighted by recency and confidence)
- Sentiment momentum and volatility
- News and social media volume analysis
- Sentiment consensus measurement
- Trading signal generation

**Usage:**
```python
from data_service.ai import SentimentFactorCalculator

calculator = SentimentFactorCalculator()

# Calculate factors for a symbol
factor = calculator.calculate_sentiment_factors(sentiment_data, 'AAPL')
print(f"Sentiment Score: {factor.sentiment_score:.3f}")
print(f"Momentum: {factor.sentiment_momentum:.3f}")

# Generate trading signal
signal = calculator.create_sentiment_signal(factor)
print(f"Signal: {signal['signal']} (confidence: {signal['confidence']:.3f})")
```

### 3. LLMIntegration (`data_service/ai/llm_integration.py`)

**Features:**
- Multiple LLM provider support (OpenAI, local models)
- Market data analysis
- Trading signal generation
- Risk assessment
- Portfolio optimization
- Trading Q&A

**Usage:**
```python
from data_service.ai import LLMIntegration

llm = LLMIntegration(provider="openai", api_key="your-key")

# Market analysis
insight = llm.analyze_market_data(market_data, ['AAPL', 'GOOGL'])

# Signal generation
signal = llm.generate_trading_signals(factor_data, price_data)

# Risk assessment
risk = llm.assess_risk(portfolio_data, market_conditions)

# Q&A
response = llm.answer_trading_question("What are momentum trading strategies?")
```

### 4. LangChainAgent (`data_service/ai/langchain_agent.py`)

**Features:**
- Intelligent strategy recommendation
- Market intelligence analysis
- Automated report generation
- Multi-tool integration
- Chain-of-thought reasoning

**Usage:**
```python
from data_service.ai import LangChainAgent

agent = LangChainAgent(llm_integration, nlp_processor)

# Strategy recommendation
strategy = agent.generate_strategy_recommendation(
    market_data, sentiment_data, portfolio_data, symbols
)

# Market analysis
analysis = agent.analyze_market_intelligence(news_data, social_data, market_data)

# Automated report
report = agent.generate_automated_report(strategies, analysis, metrics)
```

## Complete Pipeline Example

```python
from data_service.ai import *

# 1. Initialize components
nlp_processor = NLPProcessor()
factor_calculator = SentimentFactorCalculator()
llm_integration = LLMIntegration(provider="openai", api_key="your-key")
agent = LangChainAgent(llm_integration, nlp_processor)

# 2. Data collection (from existing modules)
news_processor = NewsProcessor()
social_monitor = SocialMediaMonitor()

news_data = news_processor.fetch_all_news(['AAPL', 'GOOGL'], days_back=7)
social_data = social_monitor.fetch_all_social_posts(['AAPL', 'GOOGL'])

# 3. NLP processing
processed_texts = []
for item in news_data + social_data:
    text = item.title + " " + item.content if hasattr(item, 'title') else item.text
    processed = nlp_processor.preprocess_text(text)
    processed_texts.append(processed)

# 4. Sentiment factor generation
sentiment_data = []
for processed in processed_texts:
    sentiment_data.append({
        'symbol': processed.metadata.get('symbol', 'GENERAL'),
        'sentiment_score': processed.sentiment_score,
        'confidence': processed.confidence,
        'source': processed.metadata.get('source', 'unknown'),
        'timestamp': processed.timestamp
    })

sentiment_df = pd.DataFrame(sentiment_data)
factors = factor_calculator.calculate_sentiment_factor_matrix(sentiment_df, ['AAPL', 'GOOGL'])

# 5. Strategy generation
strategy = agent.generate_strategy_recommendation(
    market_data, sentiment_df, portfolio_data, ['AAPL', 'GOOGL']
)

# 6. Generate report
report = agent.generate_automated_report([strategy], market_analysis, performance_metrics)
```

## Installation

### Basic Installation
```bash
pip install -e .
```

### With AI Dependencies
```bash
pip install -e .[ai]
```

### Additional Dependencies
```bash
pip install langchain langchain-openai langchain-community
pip install spacy transformers nltk
python -m spacy download en_core_web_sm
```

## Configuration

### Environment Variables
```bash
# OpenAI Configuration
export OPENAI_API_KEY="your-openai-api-key"
export OPENAI_MODEL="gpt-3.5-turbo"

# NLP Configuration
export SPACY_MODEL="en_core_web_sm"
export TRANSFORMERS_CACHE="/path/to/cache"
```

### Configuration File
```json
{
  "nlp": {
    "use_spacy": true,
    "use_transformers": true,
    "language": "en",
    "max_text_length": 1000
  },
  "sentiment": {
    "lookback_period": 20,
    "confidence_threshold": 0.7,
    "momentum_window": 5
  },
  "llm": {
    "provider": "openai",
    "model": "gpt-3.5-turbo",
    "temperature": 0.3,
    "max_tokens": 1000
  },
  "agent": {
    "enable_tools": true,
    "memory_size": 1000,
    "max_iterations": 10
  }
}
```

## Features Implemented

### ✅ Completed Features

1. **Data Collection**
   - News API integration (Alpha Vantage, NewsAPI)
   - Social media monitoring (Twitter, Reddit)
   - RSS feed processing
   - Data cleaning and deduplication

2. **NLP Processing**
   - Text preprocessing and normalization
   - Tokenization (spaCy, NLTK)
   - Sentiment analysis (transformers, keyword-based)
   - Keyword extraction
   - Topic modeling
   - Language detection
   - Financial entity extraction

3. **Sentiment Factor Generation**
   - Weighted sentiment scoring
   - Sentiment momentum calculation
   - Sentiment volatility measurement
   - News/social volume analysis
   - Sentiment consensus metrics
   - Trading signal generation

4. **LLM Integration**
   - Multiple provider support (OpenAI, local models)
   - Market data analysis
   - Trading signal generation
   - Risk assessment
   - Portfolio optimization
   - Trading Q&A

5. **LangChain Agent**
   - Strategy recommendation generation
   - Market intelligence analysis
   - Automated report generation
   - Multi-tool integration
   - Chain-of-thought reasoning

6. **Factor Integration**
   - Sentiment factors as quantitative inputs
   - Multi-factor model support
   - Factor backtesting integration
   - Risk management integration

### 🔄 In Progress Features

1. **Advanced NLP**
   - BERTopic for advanced topic modeling
   - Named entity recognition for companies
   - Event extraction and classification
   - Multi-language support

2. **Advanced LLM**
   - Function calling for structured outputs
   - Memory and conversation management
   - Tool integration for data analysis
   - Custom prompt engineering

3. **Real-time Processing**
   - Streaming data processing
   - Real-time sentiment monitoring
   - Live trading signal generation
   - WebSocket integration

## Usage Examples

### Example 1: Basic Sentiment Analysis
```python
from data_service.ai import NLPProcessor, SentimentFactorCalculator

# Initialize components
nlp = NLPProcessor()
calculator = SentimentFactorCalculator()

# Process news articles
texts = [
    "Apple reports strong quarterly earnings",
    "Tesla faces production challenges",
    "Google announces AI breakthrough"
]

# Analyze sentiment
results = nlp.analyze_sentiment_batch(texts)
market_sentiment = nlp.calculate_market_sentiment(results)

print(f"Market Sentiment: {market_sentiment['sentiment_label']}")
print(f"Top Keywords: {market_sentiment['top_keywords']}")
```

### Example 2: Sentiment Factor Trading
```python
from data_service.ai import SentimentFactorCalculator
from data_service.factors import FactorCalculator

# Initialize calculators
sentiment_calc = SentimentFactorCalculator()
factor_calc = FactorCalculator()

# Calculate sentiment factors
sentiment_factors = sentiment_calc.calculate_sentiment_factor_matrix(
    sentiment_data, ['AAPL', 'GOOGL', 'TSLA']
)

# Combine with technical factors
technical_factors = factor_calc.calculate_all_factors(symbol, prices, volumes)

# Create multi-factor model
combined_factors = pd.concat([technical_factors, sentiment_factors], axis=1)

# Generate trading signals
signals = []
for symbol in symbols:
    factor = sentiment_factors[sentiment_factors['symbol'] == symbol].iloc[0]
    signal = sentiment_calc.create_sentiment_signal(factor)
    signals.append(signal)
```

### Example 3: LLM Strategy Generation
```python
from data_service.ai import LLMIntegration, LangChainAgent

# Initialize components
llm = LLMIntegration(provider="openai", api_key="your-key")
agent = LangChainAgent(llm)

# Generate strategy recommendation
strategy = agent.generate_strategy_recommendation(
    market_data, sentiment_data, portfolio_data, symbols
)

print(f"Strategy: {strategy.strategy_name}")
print(f"Signal: {strategy.signal}")
print(f"Confidence: {strategy.confidence}")
print(f"Reasoning: {strategy.reasoning}")
```

### Example 4: Automated Reporting
```python
from data_service.ai import LangChainAgent

# Generate automated report
report = agent.generate_automated_report(
    strategy_results, market_analysis, performance_metrics
)

print("=== Automated Trading Report ===")
print(report)
```

## Performance Considerations

### 1. Caching
```python
from data_service.storage import CacheManager

cache = CacheManager()

# Cache sentiment analysis results
def cached_sentiment_analysis(text, cache_key, ttl=3600):
    cached_result = cache.get(cache_key)
    if cached_result:
        return cached_result
    
    result = nlp_processor.preprocess_text(text)
    cache.set(cache_key, result, expire=ttl)
    return result
```

### 2. Batch Processing
```python
# Process texts in batches
def batch_process_texts(texts, batch_size=100):
    results = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        batch_results = nlp_processor.analyze_sentiment_batch(batch)
        results.extend(batch_results)
    return results
```

### 3. Cost Optimization
```python
# Monitor LLM usage costs
def track_llm_costs(responses):
    total_cost = sum(response.cost for response in responses)
    total_tokens = sum(response.tokens_used for response in responses)
    
    print(f"Total Cost: ${total_cost:.4f}")
    print(f"Total Tokens: {total_tokens}")
    print(f"Cost per Token: ${total_cost/total_tokens:.6f}")
```

## Testing

### Unit Tests
```bash
# Run NLP tests
pytest tests/test_nlp_processor.py

# Run sentiment factor tests
pytest tests/test_sentiment_factor.py

# Run LLM integration tests
pytest tests/test_llm_integration.py
```

### Integration Tests
```bash
# Run complete pipeline test
pytest tests/test_llm_nlp_pipeline.py
```

## Troubleshooting

### Common Issues

1. **spaCy Model Not Found**
   ```bash
   python -m spacy download en_core_web_sm
   ```

2. **Transformers Import Error**
   ```bash
   pip install transformers torch
   ```

3. **OpenAI API Errors**
   - Check API key validity
   - Verify account has sufficient credits
   - Check rate limits

4. **Memory Issues**
   - Use smaller batch sizes
   - Enable caching
   - Use local models for high-frequency processing

### Debug Mode
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable debug logging for all components
nlp_processor.logger.setLevel(logging.DEBUG)
llm_integration.logger.setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Features

1. **Advanced NLP**
   - Multi-language sentiment analysis
   - Advanced topic modeling (BERTopic)
   - Event extraction and classification
   - Named entity recognition

2. **Advanced LLM**
   - Function calling for structured outputs
   - Memory and conversation management
   - Custom model fine-tuning
   - Multi-modal analysis (charts, images)

3. **Real-time Processing**
   - Streaming data processing
   - Real-time sentiment monitoring
   - Live trading signal generation
   - WebSocket integration

4. **Advanced Analytics**
   - Sentiment-based risk models
   - Sentiment factor optimization
   - Cross-asset sentiment analysis
   - Sentiment-based portfolio construction

## Contributing

When adding new LLM/NLP features:

1. Follow the existing module structure
2. Add comprehensive error handling
3. Include logging for debugging
4. Add unit tests
5. Update documentation
6. Consider performance implications
7. Monitor API costs

## License

This module is part of the trading system and follows the same license terms. 