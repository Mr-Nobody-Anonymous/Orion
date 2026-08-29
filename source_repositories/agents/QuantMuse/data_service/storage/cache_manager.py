import redis
import json
import pickle
from typing import Any, Optional, Union
from datetime import datetime, timedelta
import logging

class CacheManager:
    """Redis cache manager for trading system data"""
    
    def __init__(self, host: str = 'localhost', port: int = 6379, 
                 db: int = 0, password: Optional[str] = None):
        self.redis_client = redis.Redis(
            host=host, 
            port=port, 
            db=db, 
            password=password,
            decode_responses=False  # Keep binary format
        )
        self.logger = logging.getLogger(__name__)
        
    def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set cache value"""
        try:
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value, default=str)
            else:
                serialized_value = pickle.dumps(value)
            
            self.redis_client.set(key, serialized_value, ex=expire)
            self.logger.debug(f"Cache set: {key}")
            return True
        except Exception as e:
            self.logger.error(f"Cache set error: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Get cache value"""
        try:
            value = self.redis_client.get(key)
            if value is None:
                return None
            
            # Try JSON deserialization first
            try:
                return json.loads(value)
            except:
                # If JSON fails, try pickle
                return pickle.loads(value)
        except Exception as e:
            self.logger.error(f"Cache get error: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """Delete cache key"""
        try:
            result = self.redis_client.delete(key)
            self.logger.debug(f"Cache deleted: {key}")
            return result > 0
        except Exception as e:
            self.logger.error(f"Cache delete error: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            return self.redis_client.exists(key) > 0
        except Exception as e:
            self.logger.error(f"Cache exists error: {e}")
            return False
    
    def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for key"""
        try:
            return self.redis_client.expire(key, seconds)
        except Exception as e:
            self.logger.error(f"Cache expire error: {e}")
            return False
    
    def get_market_data_key(self, symbol: str, interval: str, limit: int = 100) -> str:
        """Generate cache key for market data"""
        return f"market_data:{symbol}:{interval}:{limit}"
    
    def get_technical_indicators_key(self, symbol: str, interval: str) -> str:
        """Generate cache key for technical indicators"""
        return f"indicators:{symbol}:{interval}"
    
    def get_strategy_signals_key(self, strategy_name: str, symbol: str) -> str:
        """Generate cache key for strategy signals"""
        return f"signals:{strategy_name}:{symbol}"
    
    def clear_all(self) -> bool:
        """Clear all cache"""
        try:
            self.redis_client.flushdb()
            self.logger.info("All cache cleared")
            return True
        except Exception as e:
            self.logger.error(f"Cache clear error: {e}")
            return False 