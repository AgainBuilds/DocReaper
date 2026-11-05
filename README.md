# Academic Identity Engine (AIE)

A provenance-aware system for discovering public academic-document records, ingesting permitted documents, extracting text, computing mathematical identity fingerprints, and finding duplicate/near-duplicate candidates.

**Important:** this is a deployable foundation and a real ingestion/API implementation, not a claim that 100,000 documents have already been collected. Corpus size depends on configured sources, network access, source terms, and crawl time.

## Mathematical identity model

AIE deliberately avoids collapsing document identity into one magic scalar. It maintains independent evidence:

1. **Raw SHA-256**: exact byte identity. Different containers or metadata produce different hashes even when visible text is identical.
2. **Normalized-text SHA-256**: exact equality after Unicode NFKC normalization, case-folding, URL masking, and whitespace normalization.
3. **Shingle set**: set of token n-grams. Similarity is Jaccard: `J(A,B)=|A∩B|/|A∪B|`.
4. **SimHash-64**: locality-sensitive binary sketch. Hamming distance `d_H(a,b)=popcount(a XOR b)` is a coarse near-duplicate signal.
5. **MinHash + LSH**: scalable approximate retrieval of likely shingle-overlap candidates. Candidate retrieval is not a proof; candidates must be re-scored and, where needed, reviewed.
6. **Optional semantic layer**: install `.[semantic]` to add embedding-based relatedness. Semantic similarity identifies related content, not duplicate identity.

A document's identity is therefore a versioned feature vector, not a single number. Store both raw and normalized hashes, algorithm version, source URL, discovery timestamp, rights status, and extraction metadata.

## Features

- PDF, DOCX, PPTX, HTML and plain-text extraction.
- HTTP API for ingestion, search, document retrieval, similarity comparison and corpus stats.
- Sitemap and OAI-PMH (`oai_dc`) metadata discovery.
- Discovery queue and MinHash LSH buckets persisted in SQLite; process discovered URLs in bounded batches.
- Source provenance and rights-status fields.
- Conservative HTTPS-only fetcher with public-IP validation, redirect revalidation and download size cap.
- CLI and Docker deployment.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn academic_identity_engine.api:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation. Health check: `/health`.

## CLI

```bash
aie stats
aie ingest-text ./paper.txt --title "Example paper"
aie discover-sitemap-cmd https://repository.example.edu/sitemap.xml --max-urls 500
aie discover-oai https://repository.example.edu/oai/request --max-records 500
```

## API examples

Ingest text:

```bash
curl -X POST http://localhost:8000/v1/ingest \\
  -H 'Content-Type: application/json' \\
  -d '{"title":"Sample paper","text":"A sufficiently long document body ...","source_name":"manual","rights_status":"unknown"}'
```

Discover public sitemap URLs:

```bash
curl -X POST http://localhost:8000/v1/discovery/sitemap \\
  -H 'Content-Type: application/json' \\
  -d '{"url":"https://repository.example.edu/sitemap.xml","max_urls":1000}'
```

Process at most 20 discovered URLs:

```bash
curl -X POST http://localhost:8000/v1/discovery/process \\
  -H 'Content-Type: application/json' -d '{"limit":20}'
```

Find likely matches:

```bash
curl -X POST http://localhost:8000/v1/documents/similar \\
  -H 'Content-Type: application/json' \\
  -d '{"text":"Paste a document excerpt of at least 50 characters here...","limit":10}'
```

## Docker

```bash
cp .env.example .env
docker compose up --build -d
```

Persistent SQLite data is stored in the `aie-data` volume. This bundled release currently uses SQLite persistence and deliberately fails fast on a non-SQLite database URL. PostgreSQL is listed among optional infrastructure dependencies but a PostgreSQL storage adapter and migrations are not implemented in this release.

## Scale architecture and honest limits

The current API is suitable for a single-node pilot and controlled ingestion. It is not yet a fully production-hardened 100k+ deployment. A production corpus should add:

- PostgreSQL with migrations and partition/index strategy.
- Object storage for originals and extracted text; keep database rows compact.
- Redis/Celery or another durable queue with idempotent tasks, leases, retries and dead-letter handling.
- A multi-node LSH backend and transactional job coordination. The current SQLite LSH band buckets are persistent for a single-node deployment, but are not a distributed index.
- Distributed per-domain rate limiting, robots.txt policy enforcement, crawl budgets and source-specific terms/rights review.
- Observability (structured logs, metrics, tracing), backups, retention and deletion workflows.
- Human-reviewed evaluation set to calibrate thresholds by document type and language.

The `/v1/documents/similar` endpoint retrieves candidates from persistent SQLite LSH band buckets and re-scores those candidates. This is a meaningful single-node index, but it is not yet load-tested or optimized for a 100k+ production corpus.

## Legal and operational rules

Only crawl content you are authorized to access. Respect repository terms, robots policies, rate limits, copyright, privacy, and takedown requests. Do not bypass authentication, paywalls, CAPTCHAs, or technical access controls. A discovered metadata record does not grant permission to download its file. Record rights status and provenance for every source sighting.

## Tests

```bash
pip install -e '.[dev]'
pytest -q
```

## Project structure

```text
src/academic_identity_engine/
  api.py            FastAPI routes
  cli.py            CLI
  config.py         Environment configuration
  discovery.py      Sitemap and OAI-PMH discovery
  extraction.py     PDF/DOCX/PPTX/HTML/text extraction
  fingerprints.py   Versioned mathematical feature vector
  matching.py       MinHash/LSH candidate retrieval
  network.py        Guarded HTTPS fetch
  schemas.py        API data models
  service.py        Ingestion and matching orchestration
  storage.py        SQLite records and provenance
```
