# FieldAtlas architecture

FieldAtlas is a deterministic geographic business discovery application. Python owns query planning, source execution, normalization, matching, classification, evidence, metrics, and exports. There is no model integration or autonomous research loop.

## Phase boundaries

The supplied brief names Phase 1 and Phase 2 without defining their boundaries. This repository interprets Phase 1 as the runnable foundation (database, worker, geocoding, contracts, taxonomy, search form), and Phase 2 as end-to-end discovery (OSM adapter, observations, canonical resolution, classification, results, map, evidence, export). Bounded website enrichment is included as an optional configured capability.

## Execution

Next.js / React → FastAPI → PostgreSQL + PostGIS. FastAPI persists a job before dispatching its UUID through Redis to Celery. The worker executes a finite pipeline and commits stage progress. The browser polls the job and queries server-paginated results. Raw observations are immutable; canonical entities are job-scoped snapshots, making runs reproducible. Cross-run identity resolution is a future migration rather than implicit merging.

Pipeline: input → canonical location → taxonomy expansion → source adapters → raw observations → normalization → weighted deduplication → website enrichment → classification → evidence → metrics → canonical tables.

Unknown values remain null. Fixture records carry `is_demo=true` and are never mixed with live results. Live discovery uses OSM; fixture discovery is an explicit mode. No OSM ratings or review counts are invented.

## Repository

```
apps/web/                 Next.js interface with an explicitly labeled fixture preview
backend/app/             FastAPI, SQLAlchemy models, pipeline and Celery tasks
backend/app/taxonomy/    Editable industry YAML rules
backend/migrations/     Alembic revisions
backend/tests/          Unit and integration tests with mocked providers
render.yaml             Native managed API and worker configuration
docs/                   Architecture, contracts, schema, implementation checklist
README.md               Docker-free local and managed deployment
```

## Data model

All application primary keys are UUIDs. `users` owns `search_jobs` and `export_jobs`; a configured workspace API key identifies the initial single workspace deployment. Location resolution stores provider IDs, components, coordinates and bounds. Search queries retain original and expanded terms. Raw observations retain complete original provider payloads. Entity source links retain every observation; merge events record rule scores and signals. Canonical business entities have separate entity type, facility type, category, specialty, subspecialty and service dimensions. Contacts, locations, evidence and taxonomy links are relational. JSONB holds raw provider payloads, job request snapshots and bounded diagnostic data. Geography points have GiST indexes; job/entity and source identifiers have B-tree indexes.

## API contracts

All paths are under `/api`. Protected endpoints require `X-API-Key` if `API_KEY` is configured. Local demo commands bind the UI/API to loopback. Production must set a strong key and terminate TLS at a reverse proxy.

| Method | Path | Contract |
|---|---|---|
| GET | /locations/autocomplete?q= | Canonical location suggestions, minimum 2 characters |
| POST | /search-jobs | terms[], location, scope=city/radius, radius_km, mode=demo/live → job |
| GET | /search-jobs/{id} | stage, counts, percent, errors, query variants |
| POST | /search-jobs/{id}/cancel | Cooperative cancellation at stage/request boundaries |
| GET | /entities | job_id, page, page_size, search, filters, sort, bbox → items,total |
| GET | /entities/{id} | Entity, categories, metrics, evidence |
| GET | /entities/{id}/sources | Associated immutable source observations |
| POST | /exports | job_id, format, scope, entity_ids or filters → export ID |
| GET | /exports/{id} | Export status and authenticated download path |
| GET | /exports/{id}/download | CSV / JSON / XLSX bytes |

Errors use FastAPI's JSON `detail` contract. Invalid inputs return 422, unknown IDs 404, missing/incorrect credentials 401. OpenAPI is generated from Pydantic schemas at `/openapi.json`.

## Taxonomy format

Each YAML file has a `categories` mapping. A rule has label, dimension, synonyms, related_queries, threshold, and weighted keywords. Rules are evaluated with normalized phrase boundaries. Scores are evidence strengths, not probabilities. Exact matched phrases and weights are stored as classification evidence. Files are loaded in filename order; expansion is stable, deduplicated, limited to 8 variants per input and 30 total by default.

## Reliability and security

Source calls have bounded timeouts, retries, and result counts. Individual failures produce partially completed runs when useful results remain. Redis broker dispatch failures mark the persisted job failed. Cancellation does not erase observations. Crawl URLs are validated before every request and redirect, with public-only DNS resolution and transport address pinning, byte/time/page limits, and per-domain/global semaphores. Crawling respects robots.txt and is disabled by default. No protected directory scraping, access control bypass, proxies or CAPTCHA automation is used.

## Hosting

GitHub is the source of truth. Vercel hosts the Next.js frontend. Render/Railway hosts native Python API and Celery worker processes. Live jobs use managed PostgreSQL/PostGIS and Redis. Local demo mode uses SQLite and a single in-process executor exclusively for fictional fixtures. Export payloads are stored in the database so the API and worker do not need shared filesystem storage. No Docker workflow is required.
