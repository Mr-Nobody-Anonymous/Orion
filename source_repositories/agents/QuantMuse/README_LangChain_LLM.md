# LangChain + LLM Integration Module

This module provides advanced AI capabilities for the trading system using LangChain and Large Language Models (LLMs). It enables intelligent market analysis, trading signal generation, risk assessment, and portfolio optimization.

## Overview

The LangChain + LLM integration module offers:

- **Market Analysis**: Intelligent analysis of market data and trends
- **Signal Generation**: AI-powered trading signal generation
- **Risk Assessment**: Automated portfolio risk analysis
- **Portfolio Optimization**: LLM-driven portfolio optimization recommendations
- **Trading Q&A**: Natural language question answering for trading topics
- **Multi-Provider Support**: Support for OpenAI, local models, and other LLM providers

## Installation

### Basic Installation
```bash
pip install -e .
```

### With AI Dependencies
```bash
pip install -e .[ai]
```

### Additional LangChain Dependencies
```bash
pip install langchain langchain-openai langchain-community
```

## Quick Start

```python
from data_service.ai import LLMIntegration
import pandas as pd

# Initialize LLM integration
llm = LLMIntegration(
    provider="openai",  # or "local"
    api_key="your-openai-api-key",
    model="gpt-3.5-turbo"
)

# Analyze market data
market_data = pd.DataFrame(...)  # Your market data
insight = llm.analyze_market_data(market_data, ['AAPL', 'GOOGL'])

# Generate trading signals
factor_data = pd.DataFrame(...)  # Your factor data
price_data = pd.DataFrame(...)   # Your price data
signal = llm.generate_trading_signals(factor_data, price_data)

# Answer trading questions
response = llm.answer_trading_question(
    "What are the key factors for momentum trading?"
)
```

## Components

### 1. LLMProvider (Abstract Base Class)

Base class for different LLM providers:

```python
class LLMProvider(ABC):
    @abstractmethod
    def generate_response(self, prompt: str, **kwargs) -> LLMResponse:
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        pass
```

### 2. OpenAIProvider

OpenAI GPT model integration:

```python
from data_service.ai.llm_integration import OpenAIProvider

provider = OpenAIProvider(
    api_key="your-api-key",
    model="gpt-3.5-turbo"  # or "gpt-4"
)

response = provider.generate_response(
    "Analyze this market data...",
    temperature=0.3,
    max_tokens=1000
)
```

### 3. LocalLLMProvider

Local model integration using transformers:

```python
from data_service.ai.llm_integration import LocalLLMProvider

provider = LocalLLMProvider(
    model_name="microsoft/DialoGPT-medium"
)

response = provider.generate_response(
    "Analyze this market data...",
    temperature=0.7,
    max_length=200
)
```

### 4. LLMIntegration

Main integration class that provides trading-specific functionality:

```python
from data_service.ai import LLMIntegration

llm = LLMIntegration(
    provider="openai",
    api_key="your-api-key",
    model="gpt-3.5-turbo"
)
```

## Features

### 1. Market Analysis

Analyze market data and generate insights:

```python
# Create market data
market_data = pd.DataFrame({
    'AAPL_return': [0.01, -0.02, 0.03, ...],
    'GOOGL_return': [0.02, -0.01, 0.04, ...],
    'volume': [1000000, 1200000, 900000, ...]
})

# Analyze market
insight = llm.analyze_market_data(market_data, ['AAPL', 'GOOGL'])

print(f"Trend: {insight.content}")
print(f"Confidence: {insight.confidence}")
print(f"Reasoning: {insight.reasoning}")
```

### 2. Trading Signal Generation

Generate trading signals based on factor and price data:

```python
# Factor data
factor_data = pd.DataFrame({
    'momentum_20d': [0.05, -0.03, 0.08],
    'pe_ratio': [25.5, 30.2, 22.1],
    'roe': [0.15, 0.12, 0.18]
})

# Price data
price_data = pd.DataFrame({
    'close': [150, 148, 152],
    'volume': [1000000, 1200000, 900000]
})

# Generate signals
strategy_context = "Multi-factor momentum strategy"
signal = llm.generate_trading_signals(
    factor_data, price_data, strategy_context
)

print(f"Signal: {signal.content}")
print(f"Confidence: {signal.confidence}")
```

### 3. Risk Assessment

Assess portfolio risk using LLM:

```python
# Portfolio data
portfolio_data = {
    'total_value': 1000000,
    'positions': {
        'AAPL': {'quantity': 100, 'avg_price': 150, 'current_price': 155},
        'GOOGL': {'quantity': 50, 'avg_price': 2800, 'current_price': 2750}
    },
    'cash': 200000,
    'leverage': 1.2,
    'daily_pnl': -5000
}

# Market conditions
market_conditions = {
    'volatility_index': 25.5,
    'market_trend': 'bearish',
    'risk_factors': ['inflation_concerns', 'fed_policy_uncertainty']
}

# Assess risk
risk_insight = llm.assess_risk(portfolio_data, market_conditions)

print(f"Risk Level: {risk_insight.content}")
print(f"Recommendations: {risk_insight.reasoning}")
```

### 4. Portfolio Optimization

Generate portfolio optimization recommendations:

```python
# Current weights
current_weights = {
    'AAPL': 0.3,
    'GOOGL': 0.25,
    'MSFT': 0.2,
    'TSLA': 0.15,
    'AMZN': 0.1
}

# Factor scores
factor_scores = {
    'AAPL': {'momentum': 0.05, 'value': 0.04, 'quality': 0.15},
    'GOOGL': {'momentum': 0.03, 'value': 0.03, 'quality': 0.18},
    # ... more stocks
}

# Constraints
constraints = {
    'min_weight': 0.05,
    'max_weight': 0.4,
    'target_return': 0.12,
    'max_volatility': 0.2
}

# Optimize portfolio
optimization = llm.optimize_portfolio(
    current_weights, factor_scores, constraints
)

print(f"Optimization: {optimization.content}")
print(f"Reasoning: {optimization.reasoning}")
```

### 5. Trading Q&A

Answer trading-related questions:

```python
# Simple question
response = llm.answer_trading_question(
    "What are the key factors for momentum trading?"
)

print(f"Answer: {response.content}")
print(f"Confidence: {response.confidence}")

# Question with context
context_data = {
    'current_vix': 25.5,
    'market_conditions': 'bearish',
    'portfolio_beta': 1.1
}

response = llm.answer_trading_question(
    "How should I adjust my portfolio during high volatility?",
    context_data
)

print(f"Answer: {response.content}")
```

## Data Structures

### LLMResponse

```python
@dataclass
class LLMResponse:
    content: str              # Response content
    confidence: float         # Confidence score (0-1)
    metadata: Dict[str, Any]  # Additional metadata
    timestamp: datetime       # Response timestamp
    model_used: str          # Model name
    tokens_used: int         # Tokens consumed
    cost: float = 0.0        # Cost in USD
```

### TradingInsight

```python
@dataclass
class TradingInsight:
    insight_type: str         # 'signal', 'analysis', 'recommendation', 'risk_warning'
    content: str             # Main insight content
    confidence: float        # Confidence score (0-1)
    symbols: List[str]       # Related symbols
    timeframe: str           # Analysis timeframe
    reasoning: str           # Detailed reasoning
    timestamp: datetime      # Insight timestamp
```

## Configuration

### Environment Variables

```bash
# OpenAI Configuration
export OPENAI_API_KEY="your-openai-api-key"
export OPENAI_MODEL="gpt-3.5-turbo"

# Local Model Configuration
export LOCAL_MODEL_PATH="/path/to/local/model"
export TRANSFORMERS_CACHE="/path/to/cache"
```

### Configuration File

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-3.5-turbo",
    "api_key": "your-api-key",
    "temperature": 0.3,
    "max_tokens": 1000,
    "cache_responses": true,
    "cache_duration": 3600
  },
  "trading_prompts": {
    "market_analysis": "You are an expert financial analyst...",
    "signal_generation": "You are a quantitative trading strategist...",
    "risk_assessment": "You are a risk management expert...",
    "portfolio_optimization": "You are a portfolio optimization specialist..."
  }
}
```

## Usage Examples

### Example 1: Complete Trading Analysis Workflow

```python
from data_service.ai import LLMIntegration
from data_service.factors import FactorCalculator
import pandas as pd

# Initialize components
llm = LLMIntegration(provider="openai", api_key="your-key")
factor_calc = FactorCalculator()

# Get market data
symbols = ['AAPL', 'GOOGL', 'MSFT']
price_data = get_market_data(symbols)  # Your data fetching function

# Calculate factors
factor_data = {}
for symbol in symbols:
    factors = factor_calc.calculate_all_factors(symbol, price_data[symbol])
    factor_data[symbol] = factors

# 1. Market Analysis
market_insight = llm.analyze_market_data(price_data, symbols)
print(f"Market Analysis: {market_insight.content}")

# 2. Signal Generation
signal_insight = llm.generate_trading_signals(factor_data, price_data)
print(f"Trading Signal: {signal_insight.content}")

# 3. Risk Assessment
portfolio_data = get_portfolio_data()  # Your portfolio function
risk_insight = llm.assess_risk(portfolio_data, market_conditions)
print(f"Risk Assessment: {risk_insight.content}")

# 4. Portfolio Optimization
current_weights = get_current_weights()  # Your weights function
optimization = llm.optimize_portfolio(current_weights, factor_data)
print(f"Optimization: {optimization.content}")
```

### Example 2: Interactive Trading Assistant

```python
def trading_assistant():
    llm = LLMIntegration(provider="openai", api_key="your-key")
    
    print("Trading Assistant - Ask me anything about trading!")
    print("Type 'quit' to exit")
    
    while True:
        question = input("\nYour question: ")
        if question.lower() == 'quit':
            break
        
        try:
            response = llm.answer_trading_question(question)
            print(f"\nAnswer: {response.content}")
            print(f"Confidence: {response.confidence:.2f}")
            print(f"Model: {response.model_used}")
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    trading_assistant()
```

### Example 3: Automated Trading Signal Generation

```python
def generate_daily_signals():
    llm = LLMIntegration(provider="openai", api_key="your-key")
    
    # Get daily market data
    symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN']
    market_data = get_daily_data(symbols)
    factor_data = calculate_daily_factors(symbols)
    
    # Generate signals for each symbol
    signals = {}
    for symbol in symbols:
        symbol_factors = factor_data[symbol]
        symbol_prices = market_data[symbol]
        
        insight = llm.generate_trading_signals(
            symbol_factors, symbol_prices,
            f"Daily momentum strategy for {symbol}"
        )
        
        signals[symbol] = {
            'signal': insight.content,
            'confidence': insight.confidence,
            'reasoning': insight.reasoning
        }
    
    # Save signals
    save_signals_to_database(signals)
    return signals

# Run daily signal generation
daily_signals = generate_daily_signals()
```

## Performance Considerations

### 1. Caching

Implement caching to reduce API calls:

```python
from data_service.storage import CacheManager

cache = CacheManager()

def cached_llm_call(llm, prompt, cache_key, ttl=3600):
    # Check cache first
    cached_response = cache.get(cache_key)
    if cached_response:
        return cached_response
    
    # Make LLM call
    response = llm.generate_response(prompt)
    
    # Cache response
    cache.set(cache_key, response, expire=ttl)
    return response
```

### 2. Batch Processing

Process multiple requests in batches:

```python
def batch_analyze_symbols(llm, symbols, market_data):
    insights = {}
    
    # Process in batches of 5
    batch_size = 5
    for i in range(0, len(symbols), batch_size):
        batch_symbols = symbols[i:i+batch_size]
        batch_data = market_data[batch_symbols]
        
        # Analyze batch
        batch_insight = llm.analyze_market_data(batch_data, batch_symbols)
        
        # Store results
        for symbol in batch_symbols:
            insights[symbol] = batch_insight
    
    return insights
```

### 3. Cost Optimization

Monitor and optimize API costs:

```python
def track_llm_costs(llm_responses):
    total_cost = 0
    total_tokens = 0
    
    for response in llm_responses:
        total_cost += response.cost
        total_tokens += response.tokens_used
    
    print(f"Total Cost: ${total_cost:.4f}")
    print(f"Total Tokens: {total_tokens}")
    print(f"Cost per Token: ${total_cost/total_tokens:.6f}")
```

## Error Handling

### 1. API Failures

```python
def robust_llm_call(llm, prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = llm.generate_response(prompt)
            return response
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2 ** attempt)  # Exponential backoff
```

### 2. Fallback Strategies

```python
def fallback_analysis(llm, market_data, symbols):
    try:
        # Try OpenAI first
        return llm.analyze_market_data(market_data, symbols)
    except Exception as e:
        # Fallback to local model
        local_llm = LLMIntegration(provider="local")
        return local_llm.analyze_market_data(market_data, symbols)
```

## Testing

### Unit Tests

```python
import pytest
from data_service.ai import LLMIntegration

def test_llm_initialization():
    llm = LLMIntegration(provider="openai", api_key="test-key")
    assert llm.provider is not None
    assert llm.provider.get_model_info()['provider'] == 'OpenAI'

def test_market_analysis():
    llm = LLMIntegration(provider="openai", api_key="test-key")
    market_data = pd.DataFrame({'AAPL': [1, 2, 3]})
    
    insight = llm.analyze_market_data(market_data, ['AAPL'])
    assert insight.insight_type == 'analysis'
    assert insight.symbols == ['AAPL']
    assert insight.confidence >= 0
```

### Integration Tests

```python
def test_complete_workflow():
    llm = LLMIntegration(provider="openai", api_key="test-key")
    
    # Test complete workflow
    market_data = create_test_market_data()
    factor_data = create_test_factor_data()
    
    # Market analysis
    market_insight = llm.analyze_market_data(market_data, ['AAPL'])
    assert market_insight is not None
    
    # Signal generation
    signal_insight = llm.generate_trading_signals(factor_data, market_data)
    assert signal_insight is not None
    
    # Risk assessment
    portfolio_data = create_test_portfolio()
    risk_insight = llm.assess_risk(portfolio_data, {})
    assert risk_insight is not None
```

## Troubleshooting

### Common Issues

1. **API Key Errors**
   - Ensure API key is valid and has sufficient credits
   - Check environment variables are set correctly

2. **Rate Limiting**
   - Implement exponential backoff
   - Use caching to reduce API calls
   - Consider using local models for high-frequency requests

3. **Model Availability**
   - Check if the specified model is available
   - Verify API endpoint accessibility

4. **Memory Issues**
   - Local models can be memory-intensive
   - Use smaller models or cloud-based solutions

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

llm = LLMIntegration(provider="openai", api_key="your-key")
# Debug information will be logged
```

## Future Enhancements

Planned improvements:

1. **Advanced LangChain Features**
   - Chain of thought reasoning
   - Memory and conversation management
   - Tool integration for data analysis

2. **Multi-Modal Support**
   - Chart and graph analysis
   - News image processing
   - Video content analysis

3. **Custom Model Training**
   - Fine-tuned models for trading
   - Domain-specific embeddings
   - Custom prompt engineering

4. **Real-time Integration**
   - Streaming responses
   - WebSocket support
   - Real-time market analysis

5. **Advanced Analytics**
   - Sentiment analysis integration
   - Technical indicator interpretation
   - Fundamental analysis automation

## Contributing

When adding new LLM features:

1. Follow the existing provider pattern
2. Add comprehensive error handling
3. Include cost tracking
4. Add unit tests
5. Update documentation
6. Consider performance implications

## License

This module is part of the trading system and follows the same license terms. 