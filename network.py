"""Conservative public-web fetching with robots checks, host pacing and size limits."""
import asyncio, ipaddress, socket, time
from urllib.parse import urlparse, urljoin
import httpx
from .config import settings

class UnsafeURL(ValueError): pass
_host_locks: dict[str, asyncio.Lock] = {}
_host_last_request: dict[str, float] = {}

def validate_public_url(url: str) -> str:
    p = urlparse(url)
    if p.scheme != "https" or not p.hostname: raise UnsafeURL("Only absolute HTTPS URLs are accepted")
    host = p.hostname.lower()
    if host in {"localhost", "localhost.localdomain"}: raise UnsafeURL("Local hostnames are blocked")
    try: addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as e: raise UnsafeURL(f"DNS lookup failed: {e}") from e
    for item in addresses:
        ip = ipaddress.ip_address(item[4][0])
        if not ip.is_global: raise UnsafeURL("Private, loopback, link-local, and reserved IPs are blocked")
    return url

async def _pace(host: str):
    lock = _host_locks.setdefault(host, asyncio.Lock())
    async with lock:
        now = time.monotonic()
        wait = settings.crawl_delay_seconds - (now - _host_last_request.get(host, 0.0))
        if wait > 0: await asyncio.sleep(wait)
        _host_last_request[host] = time.monotonic()

async def fetch_url(url: str) -> tuple[bytes, str, str]:
    current = validate_public_url(url)
    from .robots import allowed_by_robots
    if not await allowed_by_robots(current):
        raise PermissionError("URL is disallowed by robots.txt or the robots policy could not be verified")
    headers = {"User-Agent": settings.user_agent, "Accept": "application/pdf,application/vnd.openxmlformats-officedocument.*,text/html,text/plain,*/*;q=0.5"}
    max_bytes = settings.max_download_mb * 1024 * 1024
    async with httpx.AsyncClient(timeout=settings.request_timeout, follow_redirects=False, headers=headers) as client:
        for _ in range(6):
            host = urlparse(current).hostname or ""
            await _pace(host)
            async with client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location: raise ValueError("Redirect without Location")
                    current = validate_public_url(urljoin(current, location))
                    if not await allowed_by_robots(current): raise PermissionError("Redirect target is disallowed by robots.txt")
                    continue
                response.raise_for_status()
                declared = response.headers.get("content-length")
                if declared and int(declared) > max_bytes: raise ValueError("Document exceeds configured download limit")
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > max_bytes: raise ValueError("Document exceeds configured download limit")
                    chunks.append(chunk)
                return b"".join(chunks), response.headers.get("content-type", ""), str(response.url)
    raise ValueError("Too many redirects")
