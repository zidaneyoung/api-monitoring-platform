# api-monitoring-platform

Local setup for the API Monitoring Platform.

## Repository structure

- `apps/web`: Next.js frontend application.
- `apps/backend`: FastAPI backend, Celery worker, and scheduler application.
- `infrastructure`: Docker, deployment, monitoring, and infrastructure configuration.
- `docs`: Product requirements, architecture decisions, and technical documentation.

## Required software

- Git 2.x
- Docker Desktop or Docker Engine with Docker Compose v2

## Clone the repository

```bash
git clone <repo-url>
cd api-monitoring-platform
```

## Create environment files

The repository keeps example env files in source control and ignores the local copies.

Copy the root Compose variables:

```bash
cp .env.example .env
```

Copy the backend environment:

```bash
cp apps/backend/.env.example apps/backend/.env
```

Copy the frontend environment:

```bash
cp apps/web/.env.example apps/web/.env.local
```

Edit the copied files before starting the stack.

For Docker Compose, the backend must talk to the container services, not `localhost`:

- `DATABASE_HOST=db`
- `REDIS_HOST=redis`
- `DATABASE_URL=postgresql://postgres:<password>@db:5432/api_monitoring`
- `REDIS_URL=redis://redis:6379/0`

The root `.env` controls the Compose database credentials and exposed web ports:

- `DATABASE_NAME`
- `DATABASE_USER`
- `DATABASE_PASSWORD`
- `BACKEND_PORT`
- `FRONTEND_PORT`

The frontend browser URL for the API stays on `http://localhost:8000` unless you change the backend port.

When running Next.js directly on the host, keep both frontend API variables on the
host address:

```dotenv
INTERNAL_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

When running through Compose, `NEXT_PUBLIC_API_BASE_URL` remains the browser-visible
host URL, while `compose.yaml` overrides `INTERNAL_API_BASE_URL` to
`http://backend:8000` for server-side route verification inside the Compose network.

## Start the stack

Start all services from the repository root:

```bash
docker compose up --build
```

Run detached if you do not want to keep the terminal attached:

```bash
docker compose up -d --build
```

What comes up:

- `db` on the internal Compose network at `db:5432`
- `redis` on the internal Compose network at `redis:6379`
- `backend` on `http://localhost:8000`
- `frontend` on `http://localhost:3000`
- `mailpit` SMTP capture on the internal network at `mailpit:1025`
- `email-worker` consuming only the `email` Celery queue

Captured development email is available in the Mailpit UI at
`http://localhost:8025` by default. Override the host UI port with
`MAILPIT_UI_PORT`; keep SMTP credentials empty and TLS disabled for this local-only
service. Production SMTP values remain environment-driven through
`apps/backend/.env`.

Health URLs:

- Backend live check: `http://localhost:8000/health/live`
- Frontend health check: `http://localhost:3000/health`

## Frontend dependency workflow

Use npm for `apps/web`. Commit `package.json` and `package-lock.json` together, and regenerate the lockfile with npm instead of editing it manually. Before changing dependencies, update the feature branch from `main` and avoid unrelated package installations.

From `apps/web`, use `npm ci` for a clean install. Use `npm install <package>` only when intentionally changing dependencies, then commit both package files.

## Migration commands

Alembic reads the same backend database settings as the application. Keep the connection in `apps/backend/.env`; do not add credentials to `apps/backend/alembic.ini`.

After starting the stack, show the current migration revision:

```bash
docker compose exec backend alembic current
```

Apply all migrations:

```bash
docker compose exec backend alembic upgrade head
```

Generate a migration after changing SQLAlchemy model metadata:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe schema change"
```

Review every generated migration before applying it. For development rollback only, revert one revision:

```bash
docker compose exec backend alembic downgrade -1
```

Reapply the reverted migration with `docker compose exec backend alembic upgrade head`.

## Stop and clean up

Stop the stack without deleting data:

```bash
docker compose down
```

Stop the stack and remove Compose volumes:

```bash
docker compose down -v --remove-orphans
```

Use the volume-removal form when you want a clean database reset.

## Troubleshooting

- Port already in use: change `BACKEND_PORT` or `FRONTEND_PORT` in the root `.env`, then rerun `docker compose up --build`.
- Backend cannot reach the database: confirm `apps/backend/.env` uses `DATABASE_HOST=db` and `DATABASE_URL` points at `db:5432`.
- Backend cannot reach Redis: confirm `apps/backend/.env` uses `REDIS_HOST=redis` and `REDIS_URL` points at `redis:6379`.
- Container startup fails: inspect logs with `docker compose logs -f backend frontend db redis worker scheduler`.
- Services are stale or unhealthy after config changes: run `docker compose down -v --remove-orphans` and start again.
- Frontend cannot call the API: confirm `apps/web/.env.local` still sets `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` or the backend port you configured.
- Authentication returns database errors after pulling new backend code: run `docker compose exec backend alembic current`, then `docker compose exec backend alembic upgrade head` if the revision is behind.
- Frontend behavior does not match the current source: rebuild the frontend image with `docker compose build --no-cache frontend`, recreate it with `docker compose up -d --force-recreate frontend`, and confirm the health endpoint before retesting.
- A bind-mounted frontend reports missing or stale packages: recreate the `frontend_node_modules` volume or run a clean `npm ci` in the same runtime that starts Next.js. Do not mix host and container `node_modules` directories.

## Notes

- Do not commit the copied local env files.
- Do not place private credentials in the example files.
