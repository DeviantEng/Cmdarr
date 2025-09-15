#!/usr/bin/env python3
"""
Common HTTP Client Utilities
Shared HTTP functionality for all API clients
"""

import aiohttp
import asyncio
import logging
from typing import Dict, Any, Optional, Union
from urllib.parse import urljoin, urlencode


class HTTPClientUtils:
    """Common HTTP utilities for API clients"""
    
    @staticmethod
    async def make_async_request(
        session: aiohttp.ClientSession,
        url: str,
        method: str = 'GET',
        params: Dict[str, str] = None,
        headers: Dict[str, str] = None,
        timeout: int = 30,
        logger: logging.Logger = None,
        json: Dict[str, Any] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        """
        Make an async HTTP request with common error handling and retry logic
        
        Args:
            session: aiohttp session
            url: Request URL
            method: HTTP method
            params: Query parameters
            headers: Request headers
            timeout: Request timeout
            logger: Logger instance
            json: JSON data for POST requests
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (exponential backoff)
            
        Returns:
            JSON response data or None on error
        """
        if params:
            url = f"{url}?{urlencode(params)}"
        
        for attempt in range(max_retries + 1):
            try:
                # Debug logging
                if logger and json:
                    logger.debug(f"Sending {method} request to {url} with JSON data: {json}")
                    logger.debug(f"Headers: {headers}")
                
                async with session.request(method, url, headers=headers, timeout=timeout, json=json) as response:
                    if response.status in [200, 201, 204]:  # Accept success status codes
                        try:
                            data = await response.json()
                            if logger:
                                logger.debug(f"Successful {method} request to {url} (status {response.status})")
                            return data
                        except aiohttp.ContentTypeError:
                            # Some APIs return empty body on success (204)
                            if logger:
                                logger.debug(f"Successful {method} request to {url} (status {response.status}, no content)")
                            return {}
                    elif response.status == 503 and attempt < max_retries:
                        # Rate limit error - retry with exponential backoff
                        error_text = await response.text()
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        if logger:
                            logger.warning(f"Rate limit error {response.status} on attempt {attempt + 1}/{max_retries + 1}: {error_text}")
                            logger.info(f"Retrying in {wait_time:.1f} seconds...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        error_text = await response.text()
                        if logger:
                            logger.error(f"HTTP error {response.status}: {error_text}")
                        return None
                        
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    wait_time = retry_delay * (2 ** attempt)
                    if logger:
                        logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries + 1}, retrying in {wait_time:.1f} seconds...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    if logger:
                        logger.error(f"Timeout connecting to {url} after {max_retries + 1} attempts")
                    return None
            except aiohttp.ClientError as e:
                if attempt < max_retries:
                    wait_time = retry_delay * (2 ** attempt)
                    if logger:
                        logger.warning(f"Client error on attempt {attempt + 1}/{max_retries + 1}: {e}, retrying in {wait_time:.1f} seconds...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    if logger:
                        logger.error(f"HTTP error connecting to {url}: {e}")
                    return None
            except Exception as e:
                if logger:
                    logger.error(f"Unexpected error with {url}: {e}")
                return None
        
        return None
    
    @staticmethod
    def build_api_url(base_url: str, endpoint: str) -> str:
        """Build API URL from base URL and endpoint"""
        return urljoin(base_url.rstrip('/') + '/', endpoint.lstrip('/'))
    
    @staticmethod
    def create_headers(api_key: str = None, content_type: str = 'application/json', **kwargs) -> Dict[str, str]:
        """Create common headers for API requests"""
        headers = {'Content-Type': content_type}
        
        if api_key:
            headers['X-Api-Key'] = api_key
        
        headers.update(kwargs)
        return headers
    
    @staticmethod
    def handle_api_error(response_data: Dict[str, Any], service_name: str, logger: logging.Logger = None) -> bool:
        """
        Handle common API error patterns
        
        Args:
            response_data: Response data from API
            service_name: Name of the service for logging
            logger: Logger instance
            
        Returns:
            True if error was handled, False if no error
        """
        if 'error' in response_data:
            error_code = response_data.get('error')
            error_message = response_data.get('message', 'Unknown error')
            
            if logger:
                if error_code == 6:  # Common "not found" error
                    logger.debug(f"{service_name} resource not found: {error_message}")
                else:
                    logger.warning(f"{service_name} API error {error_code}: {error_message}")
            
            return True
        
        return False
    
    @staticmethod
    def create_auth_headers(token: str = None, api_key: str = None, **kwargs) -> Dict[str, str]:
        """Create authentication headers for different API types"""
        headers = {'Content-Type': 'application/json'}
        
        if token:
            headers['Authorization'] = f'Token {token}'
        elif api_key:
            headers['X-Api-Key'] = api_key
        
        headers.update(kwargs)
        return headers
    
    @staticmethod
    def create_user_agent(user_agent: str, contact: str = None) -> str:
        """Create user agent string for APIs that require it"""
        if contact:
            return f'{user_agent} ({contact})'
        return user_agent
    
    @staticmethod
    def is_successful_response(response_data: Dict[str, Any]) -> bool:
        """Check if API response indicates success"""
        # Check for common error indicators
        if 'error' in response_data:
            return False
        if 'status' in response_data and response_data['status'] != 'success':
            return False
        return True
    
    @staticmethod
    def extract_error_message(response_data: Dict[str, Any]) -> Optional[str]:
        """Extract error message from API response"""
        if 'error' in response_data:
            return response_data.get('message', f"Error {response_data.get('error')}")
        if 'message' in response_data:
            return response_data['message']
        return None


class HTTPRequestBuilder:
    """Builder pattern for constructing HTTP requests"""
    
    def __init__(self, base_url: str, logger: logging.Logger = None):
        self.base_url = base_url.rstrip('/')
        self.logger = logger
        self._endpoint = ''
        self._method = 'GET'
        self._params = {}
        self._headers = {}
        self._timeout = 30
    
    def endpoint(self, endpoint: str) -> 'HTTPRequestBuilder':
        """Set the API endpoint"""
        self._endpoint = endpoint.lstrip('/')
        return self
    
    def method(self, method: str) -> 'HTTPRequestBuilder':
        """Set the HTTP method"""
        self._method = method.upper()
        return self
    
    def params(self, **kwargs) -> 'HTTPRequestBuilder':
        """Add query parameters"""
        self._params.update(kwargs)
        return self
    
    def headers(self, **kwargs) -> 'HTTPRequestBuilder':
        """Add headers"""
        self._headers.update(kwargs)
        return self
    
    def timeout(self, seconds: int) -> 'HTTPRequestBuilder':
        """Set request timeout"""
        self._timeout = seconds
        return self
    
    def auth_token(self, token: str) -> 'HTTPRequestBuilder':
        """Add authentication token"""
        self._headers['Authorization'] = f'Token {token}'
        return self
    
    def api_key(self, key: str) -> 'HTTPRequestBuilder':
        """Add API key"""
        self._headers['X-Api-Key'] = key
        return self
    
    def user_agent(self, user_agent: str, contact: str = None) -> 'HTTPRequestBuilder':
        """Add user agent"""
        self._headers['User-Agent'] = HTTPClientUtils.create_user_agent(user_agent, contact)
        return self
    
    async def execute(self, session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
        """Execute the built request"""
        url = f"{self.base_url}/{self._endpoint}"
        
        return await HTTPClientUtils.make_async_request(
            session=session,
            url=url,
            method=self._method,
            params=self._params,
            headers=self._headers,
            timeout=self._timeout,
            logger=self.logger
        )
    
    def build_url(self) -> str:
        """Build the final URL for the request"""
        url = f"{self.base_url}/{self._endpoint}"
        if self._params:
            url = f"{url}?{urlencode(self._params)}"
        return url
