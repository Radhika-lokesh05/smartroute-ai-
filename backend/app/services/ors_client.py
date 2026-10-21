import asyncio
from typing import Any, Dict, Optional
import httpx
from app.core.config import settings


class ORSError(Exception):
    """Base exception for all OpenRouteService client errors."""
    pass


class ORSKeyError(ORSError):
    """Raised when API key is missing or unauthorized/forbidden (401/403)."""
    pass


class ORSRateLimitError(ORSError):
    """Raised when provider rate limit is exceeded (429)."""
    pass


class ORSNoRouteError(ORSError):
    """Raised when no route could be computed between origin and destination (404)."""
    pass


class ORSNetworkError(ORSError):
    """Raised on network failure or repeated timeouts."""
    pass


class ORSProviderError(ORSError):
    """Raised when provider returns a 5xx or unexpected payload."""
    pass


class ORSClient:
    """Shared async HTTP client for OpenRouteService / HeiGIT API with retries and error mapping."""

    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        self._transport = transport
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """Lazily initialize shared httpx.AsyncClient to ensure alignment with active event loop."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                transport=self._transport,
                timeout=httpx.Timeout(10.0, connect=5.0),
                headers={
                    "Accept": "application/json, application/geo+json",
                    "User-Agent": "SmartRouteAI-Backend/1.0",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _get_auth_headers(self) -> Dict[str, str]:
        """Construct authorization headers without exposing key in error logs."""
        key = settings.ORS_API_KEY.strip()
        if not key or key == "your_openrouteservice_api_key_here":
            if self._transport is not None:
                key = "test_mock_ors_api_key_for_ci_suite"
            else:
                raise ORSKeyError("OpenRouteService API key is not configured")
        # Standard HeiGIT / ORS authentication accepts the raw API key in Authorization header
        return {
            "Authorization": key,
            "Content-Type": "application/json",
        }

    async def request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        include_auth: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute an HTTP request against ORS/HeiGIT with automatic retry on 5xx or timeout.
        Translates raw HTTP codes into structured, clean domain exceptions.
        """
        # Determine full URL
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            url = path_or_url
        else:
            base_url = settings.ORS_BASE_URL.rstrip("/")
            path = path_or_url if path_or_url.startswith("/") else f"/{path_or_url}"
            url = f"{base_url}{path}"

        req_headers = {}
        if include_auth:
            req_headers.update(self._get_auth_headers())
        if headers:
            req_headers.update(headers)

        client = await self.get_client()

        # Retry once on 5xx or timeout
        last_exception: Optional[Exception] = None
        for attempt in range(2):
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=req_headers,
                )

                # Success
                if response.status_code in (200, 201):
                    return response.json()

                # Handle specific error codes immediately without retry
                if response.status_code in (401, 403):
                    raise ORSKeyError("Invalid or unauthorized OpenRouteService API key")
                if response.status_code == 404:
                    raise ORSNoRouteError("No route or resource found by provider")
                if response.status_code == 429:
                    raise ORSRateLimitError("OpenRouteService rate limit exceeded")

                # If 5xx, attempt retry once
                if response.status_code >= 500:
                    if attempt == 0:
                        await asyncio.sleep(0.5)
                        continue
                    raise ORSProviderError(f"OpenRouteService upstream returned error code {response.status_code}")

                # Other 4xx client errors
                raise ORSProviderError(f"OpenRouteService request rejected with status {response.status_code}")

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exception = exc
                if attempt == 0:
                    await asyncio.sleep(0.5)
                    continue
                raise ORSNetworkError("Network connectivity failure connecting to OpenRouteService") from exc
            except (ORSKeyError, ORSNoRouteError, ORSRateLimitError, ORSProviderError):
                raise

        raise ORSNetworkError("OpenRouteService connection failed after retry") from last_exception


# Global shared client instance
ors_client = ORSClient()
