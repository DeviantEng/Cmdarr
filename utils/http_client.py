#!/usr/bin/env python3
"""
Common HTTP Client Utilities
Shared HTTP functionality for all API clients
"""

import asyncio
import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlencode, urljoin

import aiohttp


class QuotaExceededError(Exception):
    """Raised when a provider reports a long-window quota/plan violation.

    Distinct from ordinary spike/second-rate 429s: the retry window is typically
    minutes to hours rather than seconds, so callers should stop issuing requests
    to the affected provider for the remainder of the run rather than burning
    further attempts that will themselves be rejected.
    """

    def __init__(self, retry_after_seconds: float | None = None, detail: str = ""):
        super().__init__(detail or "provider quota exceeded")
        self.retry_after_seconds = retry_after_seconds
        self.detail = detail


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a Retry-After header value into seconds.

    RFC 7231 allows either an integer seconds value or an HTTP-date. Returns
    None on unparseable input so callers can fall back to their own backoff.
    """
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except TypeError, ValueError:
        pass
    try:
        dt = parsedate_to_datetime(value)
    except TypeError, ValueError:
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return max(0.0, (dt - datetime.now(UTC)).total_seconds())


class HTTPClientUtils:
    """Common HTTP utilities for API clients"""

    @staticmethod
    async def make_async_request(
        session: aiohttp.ClientSession,
        url: str,
        method: str = "GET",
        params: dict[str, str] = None,
        headers: dict[str, str] = None,
        timeout: int = 30,
        logger: logging.Logger = None,
        json: dict[str, Any] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        suppress_error_log_statuses: frozenset[int] | set[int] | None = None,
    ) -> dict[str, Any] | None:
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

                async with session.request(
                    method, url, headers=headers, timeout=timeout, json=json
                ) as response:
                    if response.status in [200, 201, 204]:  # Accept success status codes
                        try:
                            data = await response.json()
                            if logger:
                                logger.debug(
                                    f"Successful {method} request to {url} (status {response.status})"
                                )
                            return data
                        except aiohttp.ContentTypeError:
                            # Some APIs return empty body on success (204)
                            if logger:
                                logger.debug(
                                    f"Successful {method} request to {url} (status {response.status}, no content)"
                                )
                            return {}
                    elif response.status in (429, 503):
                        # Rate limit (429) or service unavailable (503).
                        #
                        # Two flavors of 429 matter here:
                        #   - Short-window spike arrest / per-second burst: clears in
                        #     seconds, so we retry with exponential backoff (floored at 2s
                        #     to clear the typical 1s spike-arrest window) honoring any
                        #     Retry-After header.
                        #   - Long-window quota/plan violation: clears in minutes to hours.
                        #     Retrying in-session is counterproductive (each retry also
                        #     counts against the quota and delays the run). Surface as
                        #     QuotaExceededError so the caller can disable the provider
                        #     for the remainder of the run.
                        error_text = await response.text()
                        retry_after_hdr = response.headers.get(
                            "Retry-After"
                        ) or response.headers.get("retry-after")
                        retry_after_sec = _parse_retry_after(retry_after_hdr)

                        is_quota = response.status == 429 and (
                            "quota" in error_text.lower()
                            or (retry_after_sec is not None and retry_after_sec > 60.0)
                        )
                        if is_quota:
                            if logger:
                                logger.error(
                                    "Quota/plan 429 on %s (Retry-After=%s): %s",
                                    url,
                                    retry_after_hdr,
                                    error_text[:300],
                                )
                            raise QuotaExceededError(
                                retry_after_seconds=retry_after_sec,
                                detail=error_text[:500],
                            )

                        if attempt >= max_retries:
                            if logger:
                                logger.error(
                                    "Rate limit %s exhausted retries (%s/%s): %s",
                                    response.status,
                                    attempt + 1,
                                    max_retries + 1,
                                    error_text[:300],
                                )
                            return None

                        wait_time = retry_delay * (2**attempt)
                        if retry_after_sec is not None:
                            wait_time = max(wait_time, retry_after_sec)
                        if response.status == 429:
                            wait_time = max(wait_time, 2.0)
                        if logger:
                            logger.warning(
                                f"Rate limit error {response.status} on attempt {attempt + 1}/{max_retries + 1}: {error_text}"
                            )
                            logger.info(f"Retrying in {wait_time:.1f} seconds...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        error_text = await response.text()
                        quiet = suppress_error_log_statuses or set()
                        if logger:
                            if response.status not in quiet:
                                logger.error(f"HTTP error {response.status}: {error_text}")
                            else:
                                logger.debug(
                                    "HTTP %s (suppressed client error log): %s",
                                    response.status,
                                    error_text[:300],
                                )
                            if response.status == 403 and "bandsintown" in url.lower():
                                logger.error(
                                    "Bandsintown 403: app_id may be invalid, revoked, or not allowed for "
                                    "this use. Keys from Bandsintown for Artists are tied to one artist; "
                                    "library-wide or high-volume use may require Bandsintown partnership "
                                    "approval. See Config → Event Sources (ARTIST_EVENTS_BANDSINTOWN_APP_ID)."
                                )
                        return None

            except TimeoutError:
                if attempt < max_retries:
                    wait_time = retry_delay * (2**attempt)
                    if logger:
                        logger.warning(
                            f"Timeout on attempt {attempt + 1}/{max_retries + 1}, retrying in {wait_time:.1f} seconds..."
                        )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    if logger:
                        logger.error(
                            f"Timeout connecting to {url} after {max_retries + 1} attempts"
                        )
                    return None
            except aiohttp.ClientError as e:
                if attempt < max_retries:
                    wait_time = retry_delay * (2**attempt)
                    if logger:
                        logger.warning(
                            f"Client error on attempt {attempt + 1}/{max_retries + 1}: {e}, retrying in {wait_time:.1f} seconds..."
                        )
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
        return urljoin(base_url.rstrip("/") + "/", endpoint.lstrip("/"))

    @staticmethod
    def create_headers(
        api_key: str = None, content_type: str = "application/json", **kwargs
    ) -> dict[str, str]:
        """Create common headers for API requests"""
        headers = {"Content-Type": content_type}

        if api_key:
            headers["X-Api-Key"] = api_key

        headers.update(kwargs)
        return headers

    @staticmethod
    def handle_api_error(
        response_data: dict[str, Any], service_name: str, logger: logging.Logger = None
    ) -> bool:
        """
        Handle common API error patterns

        Args:
            response_data: Response data from API
            service_name: Name of the service for logging
            logger: Logger instance

        Returns:
            True if error was handled, False if no error
        """
        if "error" in response_data:
            error_code = response_data.get("error")
            error_message = response_data.get("message", "Unknown error")

            if logger:
                if error_code == 6:  # Common "not found" error
                    logger.debug(f"{service_name} resource not found: {error_message}")
                else:
                    logger.warning(f"{service_name} API error {error_code}: {error_message}")

            return True

        return False

    @staticmethod
    def create_auth_headers(token: str = None, api_key: str = None, **kwargs) -> dict[str, str]:
        """Create authentication headers for different API types"""
        headers = {"Content-Type": "application/json"}

        if token:
            headers["Authorization"] = f"Token {token}"
        elif api_key:
            headers["X-Api-Key"] = api_key

        headers.update(kwargs)
        return headers

    @staticmethod
    def create_user_agent(user_agent: str, contact: str = None) -> str:
        """Create user agent string for APIs that require it"""
        if contact:
            return f"{user_agent} ({contact})"
        return user_agent

    @staticmethod
    def is_successful_response(response_data: dict[str, Any]) -> bool:
        """Check if API response indicates success"""
        # Check for common error indicators
        if "error" in response_data:
            return False
        if "status" in response_data and response_data["status"] != "success":
            return False
        return True

    @staticmethod
    def extract_error_message(response_data: dict[str, Any]) -> str | None:
        """Extract error message from API response"""
        if "error" in response_data:
            return response_data.get("message", f"Error {response_data.get('error')}")
        if "message" in response_data:
            return response_data["message"]
        return None


class HTTPRequestBuilder:
    """Builder pattern for constructing HTTP requests"""

    def __init__(self, base_url: str, logger: logging.Logger = None):
        self.base_url = base_url.rstrip("/")
        self.logger = logger
        self._endpoint = ""
        self._method = "GET"
        self._params = {}
        self._headers = {}
        self._timeout = 30

    def endpoint(self, endpoint: str) -> HTTPRequestBuilder:
        """Set the API endpoint"""
        self._endpoint = endpoint.lstrip("/")
        return self

    def method(self, method: str) -> HTTPRequestBuilder:
        """Set the HTTP method"""
        self._method = method.upper()
        return self

    def params(self, **kwargs) -> HTTPRequestBuilder:
        """Add query parameters"""
        self._params.update(kwargs)
        return self

    def headers(self, **kwargs) -> HTTPRequestBuilder:
        """Add headers"""
        self._headers.update(kwargs)
        return self

    def timeout(self, seconds: int) -> HTTPRequestBuilder:
        """Set request timeout"""
        self._timeout = seconds
        return self

    def auth_token(self, token: str) -> HTTPRequestBuilder:
        """Add authentication token"""
        self._headers["Authorization"] = f"Token {token}"
        return self

    def api_key(self, key: str) -> HTTPRequestBuilder:
        """Add API key"""
        self._headers["X-Api-Key"] = key
        return self

    def user_agent(self, user_agent: str, contact: str = None) -> HTTPRequestBuilder:
        """Add user agent"""
        self._headers["User-Agent"] = HTTPClientUtils.create_user_agent(user_agent, contact)
        return self

    async def execute(self, session: aiohttp.ClientSession) -> dict[str, Any] | None:
        """Execute the built request"""
        url = f"{self.base_url}/{self._endpoint}"

        return await HTTPClientUtils.make_async_request(
            session=session,
            url=url,
            method=self._method,
            params=self._params,
            headers=self._headers,
            timeout=self._timeout,
            logger=self.logger,
        )

    def build_url(self) -> str:
        """Build the final URL for the request"""
        url = f"{self.base_url}/{self._endpoint}"
        if self._params:
            url = f"{url}?{urlencode(self._params)}"
        return url
