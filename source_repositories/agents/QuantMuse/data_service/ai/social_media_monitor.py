import requests
import pandas as pd
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta
import json
import time
from dataclasses import dataclass
import numpy as np

@dataclass
class SocialPost:
    """Social media post data structure"""
    id: str
    text: str
    author: str
    platform: str
    timestamp: datetime
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    sentiment_score: float = 0.0
    symbol: Optional[str] = None

class SocialMediaMonitor:
    """Social media sentiment monitor"""
    
    def __init__(self, api_keys: Dict[str, str] = None):
        self.api_keys = api_keys or {}
        self.logger = logging.getLogger(__name__)
        
        # Social media API endpoints
        self.social_apis = {
            'twitter': 'https://api.twitter.com/2/tweets/search/recent',
            'reddit': 'https://www.reddit.com/r/wallstreetbets/search.json',
            'stocktwits': 'https://api.stocktwits.com/api/2/streams/symbol'
        }
        
    def fetch_twitter_posts(self, query: str, max_results: int = 100) -> List[SocialPost]:
        """Fetch posts from Twitter API"""
        try:
            api_key = self.api_keys.get('twitter_bearer_token')
            if not api_key:
                self.logger.warning("Twitter API key not provided")
                return []
            
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            params = {
                'query': query,
                'max_results': max_results,
                'tweet.fields': 'created_at,public_metrics,author_id',
                'user.fields': 'username'
            }
            
            response = requests.get(self.social_apis['twitter'], 
                                  headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            posts = []
            
            if 'data' in data:
                for tweet in data['data']:
                    post = SocialPost(
                        id=tweet['id'],
                        text=tweet['text'],
                        author=tweet.get('author_id', 'unknown'),
                        platform='twitter',
                        timestamp=datetime.fromisoformat(tweet['created_at'].replace('Z', '+00:00')),
                        likes=tweet.get('public_metrics', {}).get('like_count', 0),
                        retweets=tweet.get('public_metrics', {}).get('retweet_count', 0),
                        replies=tweet.get('public_metrics', {}).get('reply_count', 0)
                    )
                    posts.append(post)
            
            self.logger.info(f"Fetched {len(posts)} Twitter posts for query: {query}")
            return posts
            
        except Exception as e:
            self.logger.error(f"Error fetching Twitter posts: {e}")
            return []
    
    def fetch_reddit_posts(self, subreddit: str, query: str, limit: int = 100) -> List[SocialPost]:
        """Fetch posts from Reddit API"""
        try:
            headers = {
                'User-Agent': 'TradingSystem/1.0'
            }
            
            params = {
                'q': query,
                'limit': limit,
                'sort': 'new',
                't': 'week'
            }
            
            url = f"https://www.reddit.com/r/{subreddit}/search.json"
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            posts = []
            
            if 'data' in data and 'children' in data['data']:
                for child in data['data']['children']:
                    post_data = child['data']
                    post = SocialPost(
                        id=post_data['id'],
                        text=post_data.get('title', '') + ' ' + post_data.get('selftext', ''),
                        author=post_data.get('author', 'unknown'),
                        platform='reddit',
                        timestamp=datetime.fromtimestamp(post_data.get('created_utc', 0)),
                        likes=post_data.get('score', 0),
                        retweets=post_data.get('num_comments', 0)
                    )
                    posts.append(post)
            
            self.logger.info(f"Fetched {len(posts)} Reddit posts from r/{subreddit}")
            return posts
            
        except Exception as e:
            self.logger.error(f"Error fetching Reddit posts: {e}")
            return []
    
    def fetch_stocktwits_posts(self, symbol: str, limit: int = 100) -> List[SocialPost]:
        """Fetch posts from StockTwits API"""
        try:
            params = {
                'symbol': symbol,
                'limit': limit
            }
            
            response = requests.get(self.social_apis['stocktwits'], params=params)
            response.raise_for_status()
            
            data = response.json()
            posts = []
            
            if 'messages' in data:
                for message in data['messages']:
                    post = SocialPost(
                        id=str(message.get('id', '')),
                        text=message.get('body', ''),
                        author=message.get('user', {}).get('username', 'unknown'),
                        platform='stocktwits',
                        timestamp=datetime.fromtimestamp(message.get('created_at', 0)),
                        likes=message.get('likes', {}).get('total', 0),
                        symbol=symbol
                    )
                    posts.append(post)
            
            self.logger.info(f"Fetched {len(posts)} StockTwits posts for {symbol}")
            return posts
            
        except Exception as e:
            self.logger.error(f"Error fetching StockTwits posts: {e}")
            return []
    
    def fetch_all_social_posts(self, symbols: List[str], 
                              platforms: List[str] = None) -> List[SocialPost]:
        """Fetch posts from all social media platforms"""
        if platforms is None:
            platforms = ['reddit', 'stocktwits']  # Twitter requires API key
        
        all_posts = []
        
        for symbol in symbols:
            # Reddit posts
            if 'reddit' in platforms:
                reddit_posts = self.fetch_reddit_posts('wallstreetbets', symbol)
                all_posts.extend(reddit_posts)
                
                reddit_posts = self.fetch_reddit_posts('stocks', symbol)
                all_posts.extend(reddit_posts)
            
            # StockTwits posts
            if 'stocktwits' in platforms:
                stocktwits_posts = self.fetch_stocktwits_posts(symbol)
                all_posts.extend(stocktwits_posts)
            
            # Twitter posts (if API key available)
            if 'twitter' in platforms and self.api_keys.get('twitter_bearer_token'):
                twitter_posts = self.fetch_twitter_posts(f"${symbol} OR #{symbol}")
                all_posts.extend(twitter_posts)
            
            # Rate limiting
            time.sleep(2)
        
        # Remove duplicates
        unique_posts = self._remove_duplicates(all_posts)
        
        self.logger.info(f"Total unique social posts: {len(unique_posts)}")
        return unique_posts
    
    def _remove_duplicates(self, posts: List[SocialPost]) -> List[SocialPost]:
        """Remove duplicate posts based on text similarity"""
        unique_posts = []
        seen_texts = set()
        
        for post in posts:
            # Simple text similarity check
            text_key = post.text[:100].lower().strip()  # First 100 chars
            if text_key not in seen_texts:
                seen_texts.add(text_key)
                unique_posts.append(post)
        
        return unique_posts
    
    def calculate_social_metrics(self, posts: List[SocialPost], 
                               symbol: str = None) -> Dict[str, float]:
        """Calculate social media engagement metrics"""
        if not posts:
            return {}
        
        # Filter by symbol if specified
        if symbol:
            posts = [p for p in posts if p.symbol == symbol]
        
        if not posts:
            return {}
        
        # Calculate engagement metrics
        total_likes = sum(p.likes for p in posts)
        total_retweets = sum(p.retweets for p in posts)
        total_replies = sum(p.replies for p in posts)
        total_engagement = total_likes + total_retweets + total_replies
        
        # Calculate sentiment
        sentiment_scores = [p.sentiment_score for p in posts if p.sentiment_score != 0]
        avg_sentiment = np.mean(sentiment_scores) if sentiment_scores else 0.0
        
        # Calculate posting frequency
        if len(posts) > 1:
            timestamps = [p.timestamp for p in posts]
            time_range = max(timestamps) - min(timestamps)
            posts_per_hour = len(posts) / (time_range.total_seconds() / 3600)
        else:
            posts_per_hour = 0.0
        
        return {
            'total_posts': len(posts),
            'total_likes': total_likes,
            'total_retweets': total_retweets,
            'total_replies': total_replies,
            'total_engagement': total_engagement,
            'avg_sentiment': avg_sentiment,
            'posts_per_hour': posts_per_hour,
            'engagement_rate': total_engagement / len(posts) if posts else 0.0
        }
    
    def filter_posts_by_engagement(self, posts: List[SocialPost], 
                                  min_engagement: int = 10) -> List[SocialPost]:
        """Filter posts by minimum engagement"""
        return [p for p in posts if (p.likes + p.retweets + p.replies) >= min_engagement]
    
    def filter_posts_by_time(self, posts: List[SocialPost], 
                           hours_back: int = 24) -> List[SocialPost]:
        """Filter posts by time (last N hours)"""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        return [p for p in posts if p.timestamp >= cutoff_time]
    
    def save_posts_to_file(self, posts: List[SocialPost], filename: str):
        """Save social posts to JSON file"""
        try:
            posts_data = []
            for post in posts:
                posts_data.append({
                    'id': post.id,
                    'text': post.text,
                    'author': post.author,
                    'platform': post.platform,
                    'timestamp': post.timestamp.isoformat(),
                    'likes': post.likes,
                    'retweets': post.retweets,
                    'replies': post.replies,
                    'sentiment_score': post.sentiment_score,
                    'symbol': post.symbol
                })
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(posts_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Saved {len(posts)} social posts to {filename}")
            
        except Exception as e:
            self.logger.error(f"Error saving social posts to file: {e}")
    
    def load_posts_from_file(self, filename: str) -> List[SocialPost]:
        """Load social posts from JSON file"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                posts_data = json.load(f)
            
            posts = []
            for post_data in posts_data:
                post = SocialPost(
                    id=post_data['id'],
                    text=post_data['text'],
                    author=post_data['author'],
                    platform=post_data['platform'],
                    timestamp=datetime.fromisoformat(post_data['timestamp']),
                    likes=post_data.get('likes', 0),
                    retweets=post_data.get('retweets', 0),
                    replies=post_data.get('replies', 0),
                    sentiment_score=post_data.get('sentiment_score', 0.0),
                    symbol=post_data.get('symbol')
                )
                posts.append(post)
            
            self.logger.info(f"Loaded {len(posts)} social posts from {filename}")
            return posts
            
        except Exception as e:
            self.logger.error(f"Error loading social posts from file: {e}")
            return [] 