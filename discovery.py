from __future__ import annotations
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
import httpx
from .network import validate_public_url
from .config import settings

async def discover_sitemap(sitemap_url: str, max_urls: int = 10000) -> list[dict]:
    validate_public_url(sitemap_url)
    async with httpx.AsyncClient(timeout=settings.request_timeout, headers={"User-Agent": settings.user_agent}, follow_redirects=False) as client:
        response = await client.get(sitemap_url); response.raise_for_status()
    root = ET.fromstring(response.content)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    records = []
    for node in root.findall(".//sm:url", ns):
        loc = node.findtext("sm:loc", namespaces=ns)
        if loc:
            try: validate_public_url(loc)
            except ValueError: continue
            records.append({"url": loc, "title": None, "source": "sitemap", "metadata": {"lastmod": node.findtext("sm:lastmod", namespaces=ns)}})
            if len(records) >= max_urls: break
    # Sitemap index files are intentionally not recursively expanded in this simple method.
    return records

async def discover_oai_pmh(base_url: str, set_spec: str | None = None, max_records: int = 1000) -> list[dict]:
    validate_public_url(base_url)
    params = {"verb": "ListRecords", "metadataPrefix": "oai_dc"}
    if set_spec: params["set"] = set_spec
    records, token = [], None
    async with httpx.AsyncClient(timeout=settings.request_timeout, headers={"User-Agent": settings.user_agent}) as client:
        while len(records) < max_records:
            query = {"verb": "ListRecords", "resumptionToken": token} if token else params
            response = await client.get(base_url, params=query); response.raise_for_status()
            root = ET.fromstring(response.content)
            ns = {"oai": "http://www.openarchives.org/OAI/2.0/", "dc": "http://purl.org/dc/elements/1.1/"}
            for rec in root.findall(".//oai:record", ns):
                header = rec.find("oai:header", ns)
                if header is not None and header.attrib.get("status") == "deleted": continue
                metadata = rec.find("oai:metadata", ns)
                if metadata is None: continue
                vals = lambda tag: [x.text for x in metadata.findall(f".//dc:{tag}", ns) if x.text]
                ids = vals("identifier")
                urls = [x for x in ids if x.startswith("https://")]
                title = next(iter(vals("title")), None)
                if urls:
                    try: validate_public_url(urls[0])
                    except ValueError: continue
                    records.append({"url": urls[0], "title": title, "source": "oai-pmh", "metadata": {"authors": vals("creator"), "subjects": vals("subject"), "dates": vals("date"), "identifiers": ids}})
                    if len(records) >= max_records: break
            rt = root.find(".//oai:resumptionToken", ns)
            token = (rt.text or "").strip() if rt is not None else ""
            if not token: break
    return records
