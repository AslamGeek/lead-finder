# lead-finder

## Deployment status

This repository was empty when inspected on 2026-09-10: it had no commits, branches, application files, dependency manifests, Docker files, or deployment configuration. This README records deployment readiness; it is not an implemented application.

GitHub is the source of truth. No application code from another workspace has been copied here.

## Docker-free deployment target

Once the existing source is committed, retain its layout and configure only components it actually contains:

```text
GitHub: AslamGeek/lead-finder
  |
  +-- Vercel: existing frontend, if present
  |
  +-- Managed backend host: existing backend, only if present
        |
        +-- Managed PostgreSQL/PostGIS: only if already used
        +-- Managed Redis and workers: only if already used
```

Docker is not required. There is no Docker workflow to remove. No backend, database, queue, worker, migrations, routes, or product features have been introduced.

## Deployment blockers

| Item | Verified state | Required next step |
| --- | --- | --- |
| Frontend root and framework | No source or package manifest | Commit the existing frontend before selecting its Vercel root/framework |
| Build and local startup | No scripts or lockfile | Use the existing application's commands after source is available |
| Backend and start command | No backend or entry point | Inspect the actual backend before selecting a host or command |
| PostgreSQL/PostGIS | No database implementation | Configure managed PostgreSQL/PostGIS only if already used |
| Redis and workers | No queue or worker implementation | Configure managed services only if existing code requires them |
| Database migrations | No migration configuration or revisions | Preserve the actual migration framework; do not fabricate migrations |
| API URL and CORS | No API client or server | Configure the existing client and exact trusted origins after inspection |
| Automatic deployments | No deployable application | Connect the source-bearing repository to the appropriate hosts |
| Verification | No application or tests to execute | Run existing build, startup checks and tests after source is committed |

## Environment variables

No runtime variables can be confirmed as required yet. Never commit secrets.

If the existing frontend is Next.js and calls a separate backend, preserve its API URL variable, or introduce `NEXT_PUBLIC_API_BASE_URL` when needed for deployment compatibility. Production and preview values must point to the appropriate HTTPS API. Never put backend credentials in a `NEXT_PUBLIC_` variable.

Configure database URLs, Redis URLs, allowed origins and service keys only for components actually present. CORS should allow exact trusted production, custom and preview origins; do not trust every Vercel tenant.

## Deployment steps after source is available

1. Commit the existing application to this repository without rebuilding or restructuring it.
2. Inspect its manifests, scripts, routes, environment usage and any Docker configuration to identify deployment requirements.
3. Import this repository in Vercel. Select the verified frontend root and its existing install/build commands. Set Development, Preview and Production variables separately. See [Vercel monorepos](https://vercel.com/docs/monorepos) and [environment variables](https://vercel.com/docs/environment-variables).
4. If a backend exists, connect this repository to a native runtime on Render or Railway. Set its verified root, install and start commands. Keep workers separate only if already implemented. See [Render native deployments](https://render.com/docs/deploys).
5. Provision managed database/queue services only if required by the source. Run existing migrations once during deployment; do not recreate the schema manually.
6. Verify preview and production builds, backend startup, HTTPS, CORS, migrations and existing tests before declaring deployment complete.

No frontend, backend, worker or migration command is supplied because none exists in the inspected source. No Vercel, Render, Railway, database or Redis service has been provisioned or deployed.
