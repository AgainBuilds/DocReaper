from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel, Field
from .config import settings
from .storage import Store
from .service import Engine
from .schemas import DocumentIngest, SimilarityRequest

store = Store(settings.database_url)
engine = Engine(store)

@asynccontextmanager
async def lifespan(app):
    yield
    store.close()

app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

@app.get("/", include_in_schema=False)
def dashboard(): return FileResponse(Path(__file__).parent / "static" / "index.html")

@app.get("/health")
def health(): return {"status": "ok", "service": "academic-identity-engine", "version": "1.0.0"}

@app.get("/v1/stats")
def stats(): return store.stats()

@app.get("/v1/documents")
def list_documents(q: str | None = None, limit: int = 25, offset: int = 0):
    if not 1 <= limit <= 100: raise HTTPException(400, "limit must be between 1 and 100")
    return store.list_documents(q, limit, max(offset, 0))

@app.get("/v1/documents/{document_id}")
def get_document(document_id: str):
    doc = store.get_document(document_id)
    if not doc: raise HTTPException(404, "Document not found")
    return doc

@app.post("/v1/ingest")
async def ingest(payload: DocumentIngest):
    try:
        if payload.text:
            return engine.ingest_text(payload.text, payload.title, str(payload.url) if payload.url else None, payload.source_name, payload.rights_status.value, payload.language, payload.metadata)
        if payload.content_base64:
            if payload.rights_status.value == "disallowed": raise HTTPException(403, "This source is marked disallowed")
            if len(payload.content_base64) > int(settings.max_download_mb * 1024 * 1024 * 4 / 3) + 8: raise HTTPException(413, "Upload exceeds configured size limit")
            return engine.ingest_base64(payload.content_base64, payload.metadata.get("filename", "upload.bin"), payload.title, payload.source_name, payload.rights_status.value)
        if payload.url:
            if payload.rights_status.value == "disallowed": raise HTTPException(403, "This source is marked disallowed")
            return await engine.ingest_url(str(payload.url), payload.title, payload.source_name, payload.rights_status.value)
        raise HTTPException(422, "Provide text, content_base64, or url")
    except HTTPException: raise
    except Exception as exc: raise HTTPException(400, str(exc)) from exc

@app.post("/v1/documents/similar")
def similar(payload: SimilarityRequest): return {"results": engine.similar(payload.text, payload.limit)}

@app.post("/v1/discovery/sitemap")
async def sitemap(payload: dict):
    from .discovery import discover_sitemap
    try:
        records = await discover_sitemap(payload["url"], min(int(payload.get("max_urls", 1000)), 10000))
        for r in records: store.add_discovery(r["url"], r["title"], r["source"], r["metadata"])
        return {"discovered": len(records)}
    except Exception as exc: raise HTTPException(400, str(exc)) from exc

@app.post("/v1/discovery/oai-pmh")
async def oai_pmh(payload: dict):
    from .discovery import discover_oai_pmh
    try:
        records = await discover_oai_pmh(payload["url"], payload.get("set"), min(int(payload.get("max_records", 1000)), 10000))
        for r in records: store.add_discovery(r["url"], r["title"], r["source"], r["metadata"])
        return {"discovered": len(records)}
    except Exception as exc: raise HTTPException(400, str(exc)) from exc

@app.post("/v1/discovery/process")
async def process_discovery(payload: dict):
    limit = min(int(payload.get("limit", 20)), 100)
    queue = store.discovery_queue(limit)
    results = {"processed": 0, "failed": 0, "items": []}
    for item in queue:
        try:
            result = await engine.ingest_url(item["url"], item["title"], item["source_name"])
            store.set_discovery_status(item["url"], "ingested")
            results["processed"] += 1
            results["items"].append({"url": item["url"], "document_id": result["document"]["id"], "duplicate_of": result["duplicate_of"]})
        except Exception as exc:
            store.set_discovery_status(item["url"], "failed")
            results["failed"] += 1
            results["items"].append({"url": item["url"], "error": str(exc)[:300]})
    return results
