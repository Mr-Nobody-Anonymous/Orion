import requests
import pandas as pd
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta
import json
import time
from dataclasses import dataclass

@dataclass
class NewsItem:
    """News item data structure"""
    title: str
    content: str
    url: str
    source: str
    published_at: datetime
    symbol: Optional[str] = None
    category: str = "general"

class NewsProcessor:
    """Financial news processor and collector"""
    
    def __init__(self, api_keys: Dict[str, str] = None):
        self.api_keys = api_keys or {}
        self.logger = logging.getLogger(__name__)
        
        # News API endpoints
        self.news_apis = {
            'alpha_vantage': 'https://www.alphavantage.co/query',
            'newsapi': 'https://newsapi.org/v2/everything',
            'finnhub': 'https://finnhub.io/api/v1/company-news'
        }
        
    def fetch_news_alpha_vantage(self, symbol: str, limit: int = 50) -> List[NewsItem]:
        """Fetch news from Alpha Vantage API"""
        try:
            api_key = self.api_keys.get('alpha_vantage')
            if not api_key:
                self.logger.warning("Alpha Vantage API key not provided")
                return []
            
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': symbol,
                'apikey': api_key,
                'limit': limit
            }
            
            response = requests.get(self.news_apis['alpha_vantage'], params=params)
            response.raise_for_status()
            
            data = response.json()
            news_items = []
            
            if 'feed' in data:
                for item in data['feed']:
                    news_item = NewsItem(
                        title=item.get('title', ''),
                        content=item.get('summary', ''),
                        url=item.get('url', ''),
                        source=item.get('source', ''),
                        published_at=datetime.fromisoformat(item.get('time_published', '')),
                        symbol=symbol,
                        category=item.get('category_within_source', 'general')
                    )
                    news_items.append(news_item)
            
            self.logger.info(f"Fetched {len(news_items)} news items for {symbol}")
            return news_items
            
        except Exception as e:
            self.logger.error(f"Error fetching news from Alpha Vantage: {e}")
            return []
    
    def fetch_news_newsapi(self, query: str, symbol: str = None, 
                          days_back: int = 7) -> List[NewsItem]:
        """Fetch news from NewsAPI"""
        try:
            api_key = self.api_keys.get('newsapi')
            if not api_key:
                self.logger.warning("NewsAPI key not provided")
                return []
            
            # Build query
            search_query = f"{query} {symbol}" if symbol else query
            
            params = {
                'q': search_query,
                'apiKey': api_key,
                'language': 'en',
                'sortBy': 'publishedAt',
                'from': (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d'),
                'pageSize': 100
            }
            
            response = requests.get(self.news_apis['newsapi'], params=params)
            response.raise_for_status()
            
            data = response.json()
            news_items = []
            
            if 'articles' in data:
                for article in data['articles']:
                    news_item = NewsItem(
                        title=article.get('title', ''),
                        content=article.get('description', ''),
                        url=article.get('url', ''),
                        source=article.get('source', {}).get('name', ''),
                        published_at=datetime.fromisoformat(article.get('publishedAt', '')),
                        symbol=symbol,
                        category='financial'
                    )
                    news_items.append(news_item)
            
            self.logger.info(f"Fetched {len(news_items)} news items for {search_query}")
            return news_items
            
        except Exception as e:
            self.logger.error(f"Error fetching news from NewsAPI: {e}")
            return []
    
    def fetch_news_finnhub(self, symbol: str, from_date: str, to_date: str) -> List[NewsItem]:
        """Fetch news from Finnhub API"""
        try:
            api_key = self.api_keys.get('finnhub')
            if not api_key:
                self.logger.warning("Finnhub API key not provided")
                return []
            
            params = {
                'symbol': symbol,
                'from': from_date,
                'to': to_date,
                'token': api_key
            }
            
            response = requests.get(self.news_apis['finnhub'], params=params)
            response.raise_for_status()
            
            data = response.json()
            news_items = []
            
            for item in data:
                news_item = NewsItem(
                    title=item.get('headline', ''),
                    content=item.get('summary', ''),
                    url=item.get('url', ''),
                    source=item.get('source', ''),
                    published_at=datetime.fromtimestamp(item.get('datetime', 0)),
                    symbol=symbol,
                    category=item.get('category', 'general')
                )
                news_items.append(news_item)
            
            self.logger.info(f"Fetched {len(news_items)} news items for {symbol}")
            return news_items
            
        except Exception as e:
            self.logger.error(f"Error fetching news from Finnhub: {e}")
            return []
    
    def fetch_all_news(self, symbols: List[str], days_back: int = 7) -> List[NewsItem]:
        """Fetch news from all available sources"""
        all_news = []
        
        for symbol in symbols:
            # Try different sources
            news_items = []
            
            # Alpha Vantage
            news_items.extend(self.fetch_news_alpha_vantage(symbol))
            
            # NewsAPI
            news_items.extend(self.fetch_news_newsapi(symbol, symbol, days_back))
            
            # Finnhub
            from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            to_date = datetime.now().strftime('%Y-%m-%d')
            news_items.extend(self.fetch_news_finnhub(symbol, from_date, to_date))
            
            all_news.extend(news_items)
            
            # Rate limiting
            time.sleep(1)
        
        # Remove duplicates based on URL
        unique_news = self._remove_duplicates(all_news)
        
        self.logger.info(f"Total unique news items: {len(unique_news)}")
        return unique_news
    
    def _remove_duplicates(self, news_items: List[NewsItem]) -> List[NewsItem]:
        """Remove duplicate news items based on URL"""
        seen_urls = set()
        unique_items = []
        
        for item in news_items:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                unique_items.append(item)
        
        return unique_items
    
    def filter_news_by_keywords(self, news_items: List[NewsItem], 
                               keywords: List[str]) -> List[NewsItem]:
        """Filter news items by keywords"""
        filtered_items = []
        
        for item in news_items:
            text = f"{item.title} {item.content}".lower()
            if any(keyword.lower() in text for keyword in keywords):
                filtered_items.append(item)
        
        return filtered_items
    
    def categorize_news(self, news_items: List[NewsItem]) -> Dict[str, List[NewsItem]]:
        """Categorize news items by type"""
        categories = {
            'earnings': [],
            'analyst_ratings': [],
            'market_moves': [],
            'regulatory': [],
            'general': []
        }
        
        keywords = {
            'earnings': ['earnings', 'quarterly', 'revenue', 'profit', 'loss'],
            'analyst_ratings': ['upgrade', 'downgrade', 'analyst', 'rating', 'target'],
            'market_moves': ['stock', 'shares', 'trading', 'market', 'price'],
            'regulatory': ['sec', 'regulation', 'compliance', 'legal', 'investigation']
        }
        
        for item in news_items:
            text = f"{item.title} {item.content}".lower()
            categorized = False
            
            for category, category_keywords in keywords.items():
                if any(keyword in text for keyword in category_keywords):
                    categories[category].append(item)
                    categorized = True
                    break
            
            if not categorized:
                categories['general'].append(item)
        
        return categories
    
    def save_news_to_file(self, news_items: List[NewsItem], filename: str):
        """Save news items to JSON file"""
        try:
            news_data = []
            for item in news_items:
                news_data.append({
                    'title': item.title,
                    'content': item.content,
                    'url': item.url,
                    'source': item.source,
                    'published_at': item.published_at.isoformat(),
                    'symbol': item.symbol,
                    'category': item.category
                })
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(news_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Saved {len(news_items)} news items to {filename}")
            
        except Exception as e:
            self.logger.error(f"Error saving news to file: {e}")
    
    def load_news_from_file(self, filename: str) -> List[NewsItem]:
        """Load news items from JSON file"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                news_data = json.load(f)
            
            news_items = []
            for item_data in news_data:
                news_item = NewsItem(
                    title=item_data['title'],
                    content=item_data['content'],
                    url=item_data['url'],
                    source=item_data['source'],
                    published_at=datetime.fromisoformat(item_data['published_at']),
                    symbol=item_data.get('symbol'),
                    category=item_data.get('category', 'general')
                )
                news_items.append(news_item)
            
            self.logger.info(f"Loaded {len(news_items)} news items from {filename}")
            return news_items
            
        except Exception as e:
            self.logger.error(f"Error loading news from file: {e}")
            return [] 