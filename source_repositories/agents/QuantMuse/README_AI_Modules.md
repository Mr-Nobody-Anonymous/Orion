# AI Modules for Trading System

This document describes the AI modules that have been added to the trading system, including LLM market sentiment analysis, intelligent API management, and vector database functionality.

## Overview

The AI modules provide advanced capabilities for:
- **Market Sentiment Analysis**: Using LLMs to analyze news and social media sentiment
- **Intelligent API Management**: Rate limiting, caching, and monitoring for external APIs
- **Vector Database**: Document storage and semantic search capabilities
- **Data Persistence**: Database and file storage for all AI-generated data

## Modules Structure

```
data_service/
├── ai/                          # AI and sentiment analysis
│   ├── __init__.py
│   ├── sentiment_analyzer.py    # LLM sentiment analysis
│   ├── news_processor.py        # News collection and processing
│   └── social_media_monitor.py  # Social media monitoring
├── api/                         # API management
│   ├── __init__.py
│   ├── api_manager.py           # Intelligent API management
│   ├── api_documentation.py     # API documentation generation
│   ├── api_testing.py           # Automated API testing
│   └── api_gateway.py           # API gateway functionality
├── vector_db/                   # Vector database
│   ├── __init__.py
│   ├── vector_store.py          # Vector database operations
│   ├── embedding_manager.py     # Embedding generation and management
│   ├── search_engine.py         # Semantic search functionality
│   └── document_processor.py    # Document processing and indexing
└── storage/                     # Data persistence
    ├── __init__.py
    ├── database_manager.py      # Database operations
    ├── file_storage.py          # File storage operations
    └── cache_manager.py         # Redis caching
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

### With Visualization Dependencies
```bash
pip install -e .[visualization]
```

### All Dependencies
```bash
pip install -e .[ai,visualization,test]
```

## Usage Examples

### 1. Market Sentiment Analysis

```python
from data_service.ai import SentimentAnalyzer, NewsProcessor
from data_service.storage import DatabaseManager

# Initialize components
sentiment_analyzer = SentimentAnalyzer(openai_api_key="your-api-key")
news_processor = NewsProcessor()
db_manager = DatabaseManager()

# Fetch news
symbols = ['BTC', 'ETH', 'AAPL']
news_items = news_processor.fetch_all_news(symbols, days_back=7)

# Analyze sentiment
sentiment_results = []
for news_item in news_items:
    sentiment = sentiment_analyzer.analyze_text_sentiment(
        news_item.title + " " + news_item.content,
        news_item.symbol
    )
    sentiment_results.append(sentiment)

# Calculate market sentiment
market_sentiment = sentiment_analyzer.calculate_market_sentiment(sentiment_results)

# Generate trading signal
signal = sentiment_analyzer.generate_sentiment_signal(market_sentiment)
print(f"Trading signal: {signal}")
```

### 2. Social Media Monitoring

```python
from data_service.ai import SocialMediaMonitor

# Initialize social media monitor
social_monitor = SocialMediaMonitor()

# Fetch social media posts
symbols = ['BTC', 'ETH']
social_posts = social_monitor.fetch_all_social_posts(symbols)

# Filter by engagement
high_engagement_posts = social_monitor.filter_posts_by_engagement(
    social_posts, min_engagement=10
)

# Calculate social metrics
social_metrics = social_monitor.calculate_social_metrics(social_posts)
print(f"Social metrics: {social_metrics}")
```

### 3. Intelligent API Management

```python
from data_service.api import APIManager
from data_service.api.api_manager import APIEndpoint

# Initialize API manager
api_manager = APIManager()

# Register API endpoint
alpha_vantage_endpoint = APIEndpoint(
    name='alpha_vantage_news',
    url='https://www.alphavantage.co/query',
    method='GET',
    headers={},
    params={'function': 'NEWS_SENTIMENT', 'apikey': 'your-api-key'},
    rate_limit=5  # 5 requests per minute
)

api_manager.register_endpoint('alpha_vantage_news', alpha_vantage_endpoint)

# Make request
response = api_manager.make_request('alpha_vantage_news', {
    'tickers': 'BTC'
})

# Get performance metrics
metrics = api_manager.get_performance_metrics()
print(f"API performance: {metrics}")
```

### 4. Vector Database

```python
from data_service.vector_db import VectorStore
from data_service.vector_db.embedding_manager import EmbeddingManager
import numpy as np

# Initialize components
vector_store = VectorStore()
embedding_manager = EmbeddingManager()

# Create sample document
document_content = "Bitcoin price reaches new all-time high"
embedding = embedding_manager.generate_embedding(document_content)

# Create vector document
from data_service.vector_db.vector_store import VectorDocument
document = VectorDocument(
    id='doc1',
    content=document_content,
    metadata={'symbol': 'BTC', 'type': 'news'},
    embedding=embedding,
    timestamp=datetime.now(),
    source='news_api'
)

# Add to vector store
vector_store.add_document(document, collection='crypto_news')

# Search similar documents
query_embedding = embedding_manager.generate_embedding("cryptocurrency market")
similar_docs = vector_store.search_similar(
    query_embedding, 
    collection='crypto_news',
    top_k=5
)

for doc, similarity in similar_docs:
    print(f"Document: {doc.content}, Similarity: {similarity:.3f}")
```

### 5. Data Persistence

```python
from data_service.storage import DatabaseManager, FileStorage, CacheManager

# Initialize storage components
db_manager = DatabaseManager()
file_storage = FileStorage()
cache_manager = CacheManager()

# Save market data
import pandas as pd
market_data = pd.DataFrame({
    'timestamp': pd.date_range('2024-01-01', periods=100, freq='H'),
    'open': np.random.randn(100),
    'high': np.random.randn(100),
    'low': np.random.randn(100),
    'close': np.random.randn(100),
    'volume': np.random.randint(1000, 10000, 100)
})

db_manager.save_market_data('BTC', market_data)

# Cache frequently accessed data
cache_manager.set('btc_price', 45000, expire=300)  # 5 minutes
cached_price = cache_manager.get('btc_price')

# Save to file
file_storage.save_market_data_csv('BTC', market_data, '1h')
```

## Configuration

### Environment Variables

Create a `.env` file with your API keys:

```env
# OpenAI API
OPENAI_API_KEY=your-openai-api-key

# Alpha Vantage API
ALPHA_VANTAGE_API_KEY=your-alpha-vantage-key

# News API
NEWS_API_KEY=your-news-api-key

# Twitter API
TWITTER_BEARER_TOKEN=your-twitter-bearer-token

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your-redis-password

# Database Configuration
DATABASE_URL=sqlite:///trading_data.db
```

### Configuration File

Create a `config.json` file:

```json
{
  "ai": {
    "openai_api_key": "your-openai-api-key",
    "use_openai": true,
    "sentiment_cache_duration": 3600
  },
  "api": {
    "rate_limit_default": 60,
    "timeout_default": 30,
    "retry_count_default": 3
  },
  "vector_db": {
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "similarity_threshold": 0.5
  },
  "storage": {
    "cache_enabled": true,
    "cache_duration": 300,
    "backup_enabled": true
  }
}
```

## Running the Example

```bash
# Run the AI sentiment analysis example
python examples/ai_sentiment_analysis.py
```

## Performance Considerations

### 1. Rate Limiting
- All API calls are rate-limited to prevent hitting API limits
- Use caching to reduce redundant API calls
- Implement exponential backoff for failed requests

### 2. Memory Management
- Vector embeddings can be memory-intensive
- Use batch processing for large datasets
- Implement cleanup for old cached data

### 3. Cost Optimization
- Use local models when possible to reduce API costs
- Implement smart caching to minimize API calls
- Monitor API usage and costs

## Error Handling

All modules include comprehensive error handling:

```python
try:
    sentiment = sentiment_analyzer.analyze_text_sentiment(text, symbol)
except Exception as e:
    logger.error(f"Sentiment analysis failed: {e}")
    # Fallback to local model or default sentiment
```

## Testing

Run tests for the AI modules:

```bash
# Run all tests
pytest tests/

# Run specific module tests
pytest tests/test_sentiment_analyzer.py
pytest tests/test_vector_store.py
pytest tests/test_api_manager.py
```

## Contributing

When adding new AI features:

1. Follow the existing module structure
2. Add comprehensive error handling
3. Include logging for debugging
4. Add unit tests
5. Update documentation
6. Consider performance implications

## Troubleshooting

### Common Issues

1. **API Key Errors**: Ensure all API keys are properly set in environment variables
2. **Rate Limiting**: Check API rate limits and adjust accordingly
3. **Memory Issues**: Monitor memory usage when processing large datasets
4. **Network Errors**: Implement retry logic for network failures

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

Planned improvements:

1. **Advanced LLM Integration**: Support for more LLM providers
2. **Real-time Streaming**: WebSocket support for real-time data
3. **Advanced Analytics**: More sophisticated sentiment analysis
4. **Machine Learning**: Integration with ML models for prediction
5. **Cloud Deployment**: Support for cloud-based vector databases 