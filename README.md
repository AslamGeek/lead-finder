# FieldAtlas / lead-finder

A deterministic local-business discovery application: Next.js frontend, FastAPI API, source adapters, provenance-preserving resolution, editable taxonomies, map, filters, and CSV/JSON/XLSX exports. No LLMs, agents, embeddings, or generative decisions are used.

## What works

- Multiple search terms, canonical geographic autocomplete, city bounds or custom radius.
- Background jobs with progress, cancellation, source errors and partial completion.
- Fictional Kadapa fixtures and a live OpenStreetMap/Overpass source.
- Immutable observations, weighted deduplication, separate category/specialty/subspecialty/service dimensions.
- Optional bounded website enrichment with robots.txt, public-IP checks, DNS pinning, redirect validation and byte limits.
- Server pagination/filtering/sorting, Leaflet clustering and viewport queries, entity evidence and source profiles.
- Selected, filtered and complete exports. Workbooks include Businesses, Categories, Sources and Search Metadata.
- Export bytes are stored in the database, so managed API and worker instances need no shared filesystem.

This is a single-workspace application. A shared backend API key protects live deployments. Per-user accounts, quotas and tenant isolation are not implemented.

## Run locally without Docker

Prerequisites: Python 3.12+, Node.js 22.13+ and npm. From the repository root:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env.local
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

On macOS/Linux, activate with `source .venv/bin/activate` and copy with `cp .env.example .env.local`.

In a second terminal:

```sh
cd apps/web
npm ci
npm run dev
```

Open http://localhost:3000. Default local demo mode uses SQLite and a bounded in-process background executor, exclusively for fictional development jobs. Press **Start discovery** to run the demo through Python; the initial table is a clearly labeled read-only fixture preview. API docs: http://127.0.0.1:8000/docs.

The live pipeline requires PostgreSQL/PostGIS and Redis; SQLite is not a substitute for live spatial discovery. Set `APP_MODE=live`, configure managed development URLs and a strong key in `backend/.env.local`, run migrations, and start Celery separately:

```sh
cd backend
alembic upgrade head
celery -A app.tasks:celery worker --loglevel=INFO --concurrency=2
```

Use a Linux/macOS worker for supported Celery production operation. Windows local demonstration does not need Celery. No Docker is required.

## Production deployment

```text
GitHub: AslamGeek/lead-finder
  ├── Vercel → apps/web (Next.js)
  └── Render → backend (native Python)
        ├── FastAPI
        └── Celery worker
              ├── Managed PostgreSQL + PostGIS
              └── Managed Redis
```

**Vercel:** Import this GitHub repository, set Root Directory to `apps/web`, use the Next.js preset, `npm ci` and `npm run build`. Set `NEXT_PUBLIC_API_BASE_URL=https://YOUR-API-HOST` separately in Preview and Production. It must be an HTTPS origin, with no `/api` suffix. Keep API keys out of public frontend environment variables. Enter the workspace API key using **Connect API**; it stays in browser memory.

**Render:** Import the root `render.yaml` as a Blueprint. It declares two native Python services; the listed Starter plans incur provider charges, so review pricing before creating them. Supply the shared variables below. The API runs migrations before deployment and the worker uses the same database and Redis. Alternatively create the two services manually with root `backend` and build command `pip install -r requirements.txt`.

| Process | Exact command (from backend) |
| --- | --- |
| API | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Worker | `celery -A app.tasks:celery worker --loglevel=INFO --concurrency=2` |
| Database migration | `alembic upgrade head` |
| Local API | `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` |
| Local frontend (from apps/web) | `npm run dev` |

Railway can run the same commands as two native services. Use provider GitHub integration for automatic deployments. No custom deployment CI is necessary.

### Required production variables

Vercel requires only `NEXT_PUBLIC_API_BASE_URL`.

Both backend services share:

| Variable | Value |
| --- | --- |
| APP_MODE | `live` |
| DATABASE_URL | Managed PostgreSQL URI using `postgresql+psycopg://`; ordinary `postgresql://` and `postgres://` are normalized. Use the provider's TLS parameters. |
| REDIS_URL | Redis protocol URL, not an HTTP REST endpoint; `rediss://` enables verified TLS. |
| API_KEY | At least 24 random characters. The Blueprint generates one shared value. |
| ALLOWED_ORIGINS | Comma-separated exact production, custom and approved preview origins. No wildcard Vercel domains. |
| USER_AGENT | Application identity with an operator contact address for public sources. |

The API host supplies `PORT`. `FRONTEND_URL` optionally adds one exact allowed origin. All source limits, geocoding keys and crawl settings are listed in `backend/.env.example`. `CRAWL_ENABLED=false` is the default; turn it on when website enrichment is wanted.

Use a managed PostgreSQL service with PostGIS enabled, such as Supabase. Prefer a direct/session connection for migrations. If PostGIS is installed in a separate schema, make that schema available on the database role's search path. The initial migration enables the extension when permitted and creates the normalized schema and GiST index. Never use `create_all` to replace production migrations.

Use a Redis-compatible service supporting Celery's Redis protocol. Configure a no-eviction policy for queue data. Keep services in compatible regions. Exports persist in PostgreSQL, without attached disks.

CORS preview setup: add the exact trusted Vercel branch/deployment origin to `ALLOWED_ORIGINS` and redeploy the API. Unlisted preview origins are intentionally rejected. CORS is not authentication; the API key is still required.

### Hosting verification

Source configuration is provided; hosting accounts, database/Redis credentials, and live provider connectivity must be configured and verified in your target environment. No paid hosting resources are provisioned by running local demo mode. See [deployment checklist](docs/CHECKLIST.md).

## Tests

```sh
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
cd ../apps/web
npm run build
npm audit
```

Tests exercise the full fictional API workflow, export consistency, taxonomy, normalization, merge rules, geography, confidence completeness, SSRF rejection and mocked public HTTP sources. They require no paid APIs. The local test suite uses SQLite only for fixture jobs; production PostGIS/Celery checks need separately configured managed test services.

## Limits and evidence

OSM coverage is incomplete; an empty result does not prove that no business exists. Ratings/review counts remain null when sources do not provide them. Demo companies and addresses are fictional and labeled as such. Phone normalization never guesses a country code. Classification signals and source URLs appear in profiles.

Queries are bounded to 30 variants and 100 observations per query. Crawling uses at most 8 pages per domain, depth 2, a configured byte cap, and 400 pages per job. Failed sources/crawls are surfaced. Cancellation is cooperative at request/stage boundaries; it may wait for the current network timeout. Job-scoped canonical entities preserve reproducibility across runs.

The application does not implement protected-directory scraping, CAPTCHA bypass, rate-limit evasion, or autonomous research.

Provider references: [Vercel repository roots](https://vercel.com/docs/monorepos), [Vercel environments](https://vercel.com/docs/environment-variables), [Render native deployments](https://render.com/docs/deploys), [Supabase PostGIS](https://supabase.com/docs/guides/database/extensions/postgis).

