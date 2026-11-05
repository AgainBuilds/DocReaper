"""Small robots.txt policy reader. Fail closed on network errors; cache per origin."""
from urllib.parse import urlparse, urlunparse
from urllib.robotparser import RobotFileParser
import httpx
from .config import settings
from .network import validate_public_url

_cache: dict[str, RobotFileParser] = {}

async def allowed_by_robots(url: str) -> bool:
    validate_public_url(url)
    parsed = urlparse(url)
    origin = urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))
    if origin not in _cache:
        parser = RobotFileParser()
        parser.set_url(origin)
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout, follow_redirects=False, headers={"User-Agent": settings.user_agent}) as client:
                response = await client.get(origin)
            if response.status_code == 404:
                parser.parse([])
            elif response.status_code == 200:
                parser.parse(response.text.splitlines())
            else:
                return False
        except Exception:
            return False
        _cache[origin] = parser
    return _cache[origin].can_fetch(settings.user_agent, url)
