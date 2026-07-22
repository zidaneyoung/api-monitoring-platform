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
