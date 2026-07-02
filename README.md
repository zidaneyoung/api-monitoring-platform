# api-monitoring-platform

Local setup for the API Monitoring Platform.

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

Health URLs:

- Backend live check: `http://localhost:8000/health/live`
- Frontend health check: `http://localhost:3000/health`

## Migration commands

Not applicable in the current repository: no migration tooling or commands are present.

The only database initialization mechanism verified from repository files is the `db` service in `compose.yaml`. The official `postgres:16.4-alpine` image creates the configured database on first startup from `DATABASE_NAME`, `DATABASE_USER`, and `DATABASE_PASSWORD`, and persists data in the `postgres_data` volume.

No repository file verifies how application tables or schema objects are created.

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

## Notes

- Do not commit the copied local env files.
- Do not place private credentials in the example files.
