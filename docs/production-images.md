# Production container images

The frontend and backend Dockerfiles use pinned base-image digests and
multi-stage builds. The final frontend image contains the Next.js standalone
server and traced runtime files. The final backend image contains only the
fully locked production Python requirements, application package, and Alembic
files. Update `apps/backend/requirements.lock` deliberately whenever the
production dependency graph changes.
Neither image copies local environment files, test suites, dependency caches,
or source-control metadata.

## Build

Run builds from the repository root:

```powershell
docker build --tag api-monitoring-frontend:local `
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.example.invalid `
  apps/web
docker build --tag api-monitoring-backend:local apps/backend
```

`NEXT_PUBLIC_API_BASE_URL` is public browser configuration embedded during the
frontend build. It must never contain credentials. Private frontend server
configuration, such as `INTERNAL_API_BASE_URL` and `SESSION_COOKIE_NAME`,
remains runtime configuration.

## Runtime commands

The backend image is shared by all Python services:

```text
Release migration:
python -m app.production_migrations upgrade

API:
uvicorn app.main:app --host 0.0.0.0 --port 8000

Check worker:
celery -A app.celery_app:celery_app worker --loglevel=info

Notification worker:
celery -A app.celery_app:celery_app worker --loglevel=info --queues=email

Scheduler:
celery -A app.celery_app:celery_app beat --loglevel=info --schedule /tmp/celerybeat-schedule
```

Inspect the connected database revision without changing it:

```text
python -m app.production_migrations current
```

All images run as UID/GID `10001`. The scheduler writes its local beat state
under `/tmp`, which is writable by the non-root runtime user. No service
requires elevated privileges.

The frontend image health check calls `/health`. The shared backend image uses
a role-neutral process-liveness check because API, worker, scheduler, and
migration containers all use it. API services should override that default
with `/health/live` for liveness and `/health/ready` for dependency readiness.
Worker and scheduler readiness is verified by starting their documented
commands and confirming they remain running while connected to isolated
PostgreSQL and Redis services.

## Production-like local verification

The isolated E2E Compose environment provides PostgreSQL, Redis, one controlled
migration process, the API, check worker, scheduler, and a test-only target
without source mounts:

```powershell
./scripts/run-e2e-tests.ps1
```

Build the frontend image separately with the intended public API URL, start it
with private runtime values, and check its health:

```powershell
docker run --detach --rm --name api-monitoring-frontend-check `
  --publish 127.0.0.1:3300:3000 `
  --env INTERNAL_API_BASE_URL=http://host.docker.internal:8800 `
  --env SESSION_COOKIE_NAME=amp_session `
  api-monitoring-frontend:local
docker inspect --format '{{json .State.Health.Status}}' api-monitoring-frontend-check
docker stop api-monitoring-frontend-check
```

Production images do not require local source mounts. Runtime secrets must be
injected through the deployment platform and must not be supplied as Docker
build arguments. The complete runtime contract and secret classification are
documented in [Production configuration](production-configuration.md).
