import requests
import json
import time
from typing import Dict, List, Any, Optional, Callable
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio
import aiohttp
import numpy as np

@dataclass
class APIEndpoint:
    """API endpoint configuration"""
    name: str
    url: str
    method: str
    headers: Dict[str, str]
    params: Dict[str, Any]
    rate_limit: int  # requests per minute
    timeout: int = 30
    retry_count: int = 3
    retry_delay: int = 1

@dataclass
class APIResponse:
    """API response wrapper"""
    status_code: int
    data: Any
    headers: Dict[str, str]
    timestamp: datetime
    endpoint: str
    response_time: float

class APIManager:
    """Intelligent API manager with rate limiting, caching, and monitoring"""
    
    def __init__(self):
        self.endpoints: Dict[str, APIEndpoint] = {}
        self.rate_limiters: Dict[str, List[datetime]] = {}
        self.response_cache: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(__name__)
        
        # Performance monitoring
        self.response_times: Dict[str, List[float]] = {}
        self.error_counts: Dict[str, int] = {}
        self.success_counts: Dict[str, int] = {}
        
    def register_endpoint(self, name: str, endpoint: APIEndpoint):
        """Register a new API endpoint"""
        self.endpoints[name] = endpoint
        self.rate_limiters[name] = []
        self.response_times[name] = []
        self.error_counts[name] = 0
        self.success_counts[name] = 0
        
        self.logger.info(f"Registered API endpoint: {name}")
    
    def make_request(self, endpoint_name: str, 
                    params: Dict[str, Any] = None,
                    use_cache: bool = True,
                    cache_duration: int = 300) -> Optional[APIResponse]:
        """Make a request to a registered endpoint"""
        if endpoint_name not in self.endpoints:
            self.logger.error(f"Endpoint not found: {endpoint_name}")
            return None
        
        endpoint = self.endpoints[endpoint_name]
        
        # Check rate limiting
        if not self._check_rate_limit(endpoint_name, endpoint.rate_limit):
            self.logger.warning(f"Rate limit exceeded for {endpoint_name}")
            return None
        
        # Check cache
        if use_cache:
            cached_response = self._get_cached_response(endpoint_name, params)
            if cached_response:
                return cached_response
        
        # Make request
        start_time = time.time()
        try:
            response = self._execute_request(endpoint, params)
            response_time = time.time() - start_time
            
            # Update metrics
            self.response_times[endpoint_name].append(response_time)
            self.success_counts[endpoint_name] += 1
            
            # Cache response
            if use_cache and response and response.status_code == 200:
                self._cache_response(endpoint_name, params, response, cache_duration)
            
            return response
            
        except Exception as e:
            response_time = time.time() - start_time
            self.error_counts[endpoint_name] += 1
            self.logger.error(f"Request failed for {endpoint_name}: {e}")
            return None
    
    def _execute_request(self, endpoint: APIEndpoint, 
                        params: Dict[str, Any] = None) -> Optional[APIResponse]:
        """Execute HTTP request"""
        try:
            # Merge parameters
            request_params = endpoint.params.copy()
            if params:
                request_params.update(params)
            
            # Make request
            if endpoint.method.upper() == 'GET':
                response = requests.get(
                    endpoint.url,
                    headers=endpoint.headers,
                    params=request_params,
                    timeout=endpoint.timeout
                )
            elif endpoint.method.upper() == 'POST':
                response = requests.post(
                    endpoint.url,
                    headers=endpoint.headers,
                    json=request_params,
                    timeout=endpoint.timeout
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {endpoint.method}")
            
            # Parse response
            try:
                data = response.json()
            except:
                data = response.text
            
            return APIResponse(
                status_code=response.status_code,
                data=data,
                headers=dict(response.headers),
                timestamp=datetime.now(),
                endpoint=endpoint.name,
                response_time=response.elapsed.total_seconds()
            )
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request exception: {e}")
            return None
    
    def _check_rate_limit(self, endpoint_name: str, rate_limit: int) -> bool:
        """Check if request is within rate limit"""
        now = datetime.now()
        window_start = now - timedelta(minutes=1)
        
        # Remove old requests outside the window
        self.rate_limiters[endpoint_name] = [
            req_time for req_time in self.rate_limiters[endpoint_name]
            if req_time > window_start
        ]
        
        # Check if we can make another request
        if len(self.rate_limiters[endpoint_name]) >= rate_limit:
            return False
        
        # Add current request
        self.rate_limiters[endpoint_name].append(now)
        return True
    
    def _get_cached_response(self, endpoint_name: str, 
                           params: Dict[str, Any] = None) -> Optional[APIResponse]:
        """Get cached response if available and not expired"""
        cache_key = self._generate_cache_key(endpoint_name, params)
        
        if cache_key in self.response_cache:
            cached = self.response_cache[cache_key]
            if datetime.now() < cached['expires_at']:
                return cached['response']
            else:
                # Remove expired cache
                del self.response_cache[cache_key]
        
        return None
    
    def _cache_response(self, endpoint_name: str, params: Dict[str, Any],
                       response: APIResponse, duration: int):
        """Cache API response"""
        cache_key = self._generate_cache_key(endpoint_name, params)
        
        self.response_cache[cache_key] = {
            'response': response,
            'expires_at': datetime.now() + timedelta(seconds=duration)
        }
    
    def _generate_cache_key(self, endpoint_name: str, 
                          params: Dict[str, Any] = None) -> str:
        """Generate cache key for endpoint and parameters"""
        if params:
            param_str = json.dumps(params, sort_keys=True)
            return f"{endpoint_name}:{param_str}"
        return endpoint_name
    
    async def make_async_request(self, endpoint_name: str,
                               params: Dict[str, Any] = None) -> Optional[APIResponse]:
        """Make asynchronous request"""
        if endpoint_name not in self.endpoints:
            self.logger.error(f"Endpoint not found: {endpoint_name}")
            return None
        
        endpoint = self.endpoints[endpoint_name]
        
        # Check rate limiting
        if not self._check_rate_limit(endpoint_name, endpoint.rate_limit):
            self.logger.warning(f"Rate limit exceeded for {endpoint_name}")
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                start_time = time.time()
                
                # Prepare request
                request_params = endpoint.params.copy()
                if params:
                    request_params.update(params)
                
                # Make request
                if endpoint.method.upper() == 'GET':
                    async with session.get(
                        endpoint.url,
                        headers=endpoint.headers,
                        params=request_params,
                        timeout=aiohttp.ClientTimeout(total=endpoint.timeout)
                    ) as response:
                        data = await response.json()
                elif endpoint.method.upper() == 'POST':
                    async with session.post(
                        endpoint.url,
                        headers=endpoint.headers,
                        json=request_params,
                        timeout=aiohttp.ClientTimeout(total=endpoint.timeout)
                    ) as response:
                        data = await response.json()
                else:
                    raise ValueError(f"Unsupported HTTP method: {endpoint.method}")
                
                response_time = time.time() - start_time
                
                # Update metrics
                self.response_times[endpoint_name].append(response_time)
                self.success_counts[endpoint_name] += 1
                
                return APIResponse(
                    status_code=response.status,
                    data=data,
                    headers=dict(response.headers),
                    timestamp=datetime.now(),
                    endpoint=endpoint.name,
                    response_time=response_time
                )
                
        except Exception as e:
            self.error_counts[endpoint_name] += 1
            self.logger.error(f"Async request failed for {endpoint_name}: {e}")
            return None
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get API performance metrics"""
        metrics = {}
        
        for endpoint_name in self.endpoints:
            response_times = self.response_times.get(endpoint_name, [])
            error_count = self.error_counts.get(endpoint_name, 0)
            success_count = self.success_counts.get(endpoint_name, 0)
            total_requests = error_count + success_count
            
            metrics[endpoint_name] = {
                'total_requests': total_requests,
                'success_rate': success_count / total_requests if total_requests > 0 else 0,
                'error_rate': error_count / total_requests if total_requests > 0 else 0,
                'avg_response_time': np.mean(response_times) if response_times else 0,
                'min_response_time': min(response_times) if response_times else 0,
                'max_response_time': max(response_times) if response_times else 0,
                'current_rate_limit': len(self.rate_limiters.get(endpoint_name, []))
            }
        
        return metrics
    
    def clear_cache(self, endpoint_name: str = None):
        """Clear response cache"""
        if endpoint_name:
            # Clear cache for specific endpoint
            keys_to_remove = [k for k in self.response_cache.keys() 
                            if k.startswith(endpoint_name)]
            for key in keys_to_remove:
                del self.response_cache[key]
        else:
            # Clear all cache
            self.response_cache.clear()
        
        self.logger.info(f"Cache cleared for {endpoint_name or 'all endpoints'}")
    
    def add_retry_logic(self, endpoint_name: str, 
                       retry_function: Callable[[APIResponse], bool]):
        """Add custom retry logic for an endpoint"""
        # This would be implemented based on specific requirements
        pass
    
    def get_endpoint_status(self, endpoint_name: str) -> Dict[str, Any]:
        """Get detailed status of an endpoint"""
        if endpoint_name not in self.endpoints:
            return {}
        
        endpoint = self.endpoints[endpoint_name]
        metrics = self.get_performance_metrics().get(endpoint_name, {})
        
        return {
            'name': endpoint_name,
            'url': endpoint.url,
            'method': endpoint.method,
            'rate_limit': endpoint.rate_limit,
            'timeout': endpoint.timeout,
            'metrics': metrics,
            'last_request': self.rate_limiters.get(endpoint_name, [])[-1] if self.rate_limiters.get(endpoint_name) else None
        } 