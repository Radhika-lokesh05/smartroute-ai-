"""
Network utilities for proxy-aware client IP extraction and security.
"""
from typing import Optional
from fastapi import Request
from app.core.config import settings


def get_client_ip(request: Request, trusted_proxy_hops: Optional[int] = None) -> str:
    """
    Extract the authentic client IP address behind reverse proxies (Render, Cloudflare, NGINX).
    
    Protects against IP spoofing:
    - Never naively trusts the first entry in X-Forwarded-For if an attacker injected it.
    - Uses trusted_proxy_hops (defaults to settings.TRUSTED_PROXY_HOPS) to count back
      from the rightmost proxy-added entries.
    - If trusted_proxy_hops=1 (default on single edge proxy), the trusted client IP is
      at index -1 of the X-Forwarded-For chain.
    - Falls back to request.client.host if X-Forwarded-For is missing or empty.
    """
    hops = trusted_proxy_hops if trusted_proxy_hops is not None else max(1, settings.TRUSTED_PROXY_HOPS)
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # Split comma-separated list of IPs
        raw_ips = [ip.strip() for ip in xff.split(",") if ip.strip()]
        if raw_ips:
            if len(raw_ips) >= hops:
                return raw_ips[-hops]
            return raw_ips[0]

    # Check Cloudflare CF-Connecting-IP as secondary source if present
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip and cf_ip.strip():
        return cf_ip.strip()

    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"
