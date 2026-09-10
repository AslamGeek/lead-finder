# Implementation and deployment checklist

## Implemented
- [x] Next.js/React interface, typed forms, query polling and canonical location selection
- [x] FastAPI contracts, job state, cancellation and error reporting
- [x] SQLAlchemy relational models and versioned Alembic schema
- [x] PostgreSQL/PostGIS live spatial queries and indexes
- [x] Celery/Redis live background tasks and a separate local fixture executor
- [x] Taxonomy expansion, normalization, deduplication, classifications and provenance
- [x] Fictional fixtures plus public OSM and Photon adapters
- [x] Optional bounded, DNS-pinned website enrichment
- [x] Results filtering/sorting/pagination, map clustering, profile evidence
- [x] CSV/JSON/XLSX selected/filtered/all exports stored in the database
- [x] Docker-free local commands and Vercel/Render configuration
- [x] Unit, mocked HTTP and end-to-end fictional workflow tests

## Operator deployment checks still required
- [ ] Configure Vercel project and managed Python API/worker accounts
- [ ] Supply managed PostgreSQL/PostGIS and Redis credentials
- [ ] Apply migrations against the target database
- [ ] Verify real Celery job execution and PostGIS radius/viewport queries
- [ ] Verify live Photon/Overpass availability and data coverage
- [ ] Verify allowed production/preview CORS origins and authentication
- [ ] Configure backups, retention and monitoring for production data
- [ ] Add per-user authentication and tenancy before a multi-tenant/public service release

These deployment checks require target hosting access. They are not claimed to have passed during the local fixture tests.

