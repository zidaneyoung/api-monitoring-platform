# Automated testing

## Isolated unit tests

Requirements:

- Python 3.12 with `apps/backend/requirements-dev.txt` installed.
- Node.js with `npm ci` completed in `apps/web`.
- No PostgreSQL, Redis, Celery broker, SMTP server, or external HTTP service.
- Keep `TEST_DATABASE_URL` unset for these commands. They must never target development or production services.

Run backend business-rule, URL, SSRF-classification, error, counter, incident-transition,
notification-lifecycle, redaction, and UTC/duration tests from `apps/backend`:

```powershell
python -m pytest tests/test_monitor_urls.py tests/test_monitor_destinations.py tests/test_monitor_state.py tests/test_monitor_worker_rules.py tests/test_notification_delivery_state.py tests/test_request_validation.py tests/test_structured_logging.py tests/test_utc_time.py -q
```

Run frontend utility tests from `apps/web`:

```powershell
npm test -- --run lib/monitor-time.test.ts lib/monitor-result.test.ts lib/monitor-navigation.test.ts lib/monitor-form-errors.test.ts lib/api-error.test.ts lib/monitor-api.test.ts lib/incident-api.test.ts
```

Both commands are non-interactive and return a nonzero exit code when any selected test fails.
Tests control DNS, HTTP results, timezones, and process state locally; they require no
production credentials or production services.

## SSRF security tests

Run destination-classification, fresh-resolution, and redirect-chain security tests
from `apps/backend`:

```powershell
python -m pytest tests/test_monitor_destinations.py tests/test_monitor_redirect_security.py -q
```

Resolvers and HTTP transports are fully controlled. Restricted, loopback, private,
link-local, metadata, multicast, reserved, and unspecified destinations are never
passed to a real socket. Each redirect target is validated before the controlled
transport can observe a request, while public IPv4, IPv6, hostname, and redirect
destinations remain accepted.

## PostgreSQL, Redis, Celery, and SMTP integration tests

Requirements:

- Docker Engine or Docker Desktop with Docker Compose v2.
- No development or production service credentials.

Run the complete backend integration suite from the repository root:

```powershell
./scripts/run-integration-tests.ps1
```

The command creates the dedicated `api-monitoring-integration-tests` Compose
project. It starts disposable PostgreSQL 16, Redis 7 database 15, and Mailpit
services without publishing host ports. The test image installs only repository
requirements, applies every Alembic migration, clears the isolated database and
Redis state, then runs the backend suite. A `finally` block removes the project
containers, network, and volumes after success or failure.

For CI, execute the same Compose lifecycle and preserve the test container exit
code:

```powershell
docker compose --project-name api-monitoring-integration-tests --file compose.integration.yaml up --build --abort-on-container-exit --exit-code-from tests
docker compose --project-name api-monitoring-integration-tests --file compose.integration.yaml down --volumes --remove-orphans
```

The test process rejects a database name without `test` or `integration`, rejects
Redis database 0, and confirms test URLs differ from application URLs. Scheduler
and worker functions use the real migrated PostgreSQL database; authentication and
rate-limit tests use the real isolated Redis service; notification templates use
local Mailpit. No production service or real recipient is contacted.

## Duplicate-processing and concurrency tests

Run the scheduler, worker, incident, and email idempotency suite in the same
isolated services:

```powershell
./scripts/run-concurrency-tests.ps1
```

The bounded concurrency cases repeat scheduler dispatch, monitor execution,
incident opening, notification claiming, and SMTP delivery races. They assert one
run per schedule, one check and counter update per run, one active incident, one
opening and recovery event/delivery, and one SMTP call. Recovery tests include
interrupted sequences; email tests cancel an in-flight SMTP attempt and verify its
durable `sending` claim prevents an unsafe automatic resend.
