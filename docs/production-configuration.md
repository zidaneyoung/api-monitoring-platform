# Production configuration

Production configuration is injected per service by the selected deployment
platform. Real values must live in that platform's encrypted secret system,
not in repository files, image layers, build arguments, workflow logs, or
shell history. The repository contains documentation-only templates at
`apps/backend/.env.production.example` and
`apps/web/.env.production.example`.

No deployment provider is selected in this repository. Creating platform
secret records and proving their access controls is therefore an external
release prerequisite, not something this code can safely guess.

## Required backend configuration

The API, monitor worker, notification worker, and scheduler receive the same
base configuration. The migration job receives it as well so Alembic can load
the application settings consistently.

| Variable | Classification | Purpose |
| --- | --- | --- |
| `ENVIRONMENT` | Non-secret | Must be `production` to enable fail-closed validation |
| `DEBUG` | Non-secret | Must be `false` |
| `FRONTEND_ORIGIN` | Non-secret | Exact credential-free HTTPS origin allowed by CORS |
| `SESSION_COOKIE_NAME` | Non-secret | Cookie name; must equal the frontend value |
| `AUTH_RATE_LIMIT_KEY_SECRET` | Secret | Independent random value of at least 32 characters used to digest rate-limit identities |
| `DATABASE_URL` | Secret | Complete `postgresql://` or `postgresql+asyncpg://` URL, including production credentials and database name |
| `REDIS_URL` | Secret when credentialed | Session and rate-limit Redis connection URL |
| `CELERY_BROKER_URL` | Secret when credentialed | Redis broker URL used by workers and scheduler |
| `CELERY_RESULT_BACKEND` | Secret when credentialed | Redis result backend URL |
| `EMAIL_HOST` | Non-secret | SMTP hostname |
| `EMAIL_PORT` | Non-secret | Positive SMTP port |
| `EMAIL_USERNAME` | Secret | SMTP login identity |
| `EMAIL_PASSWORD` | Secret | SMTP password or provider token |
| `EMAIL_FROM` | Non-secret | Verified sender address |
| `EMAIL_USE_TLS` | Non-secret | Explicit `true` or `false` according to the selected SMTP service |

All required names are checked before their values are used. Errors name only
the missing or invalid variable and never include its value. Production also
rejects non-HTTPS frontend origins, debug mode, missing browser-origin checks,
short rate-limit secrets, and malformed service URLs.

`AUTH_RATE_LIMIT_KEY_SECRET` is not a session-signing key. Sessions are opaque
random tokens stored in Redis; the application does not consume the stale
`SECRET_KEY`, `ALGORITHM`, or `ACCESS_TOKEN_EXPIRE_MINUTES` settings that were
previously present in the development template.

## Optional backend tuning

These settings have safe defaults but should be reviewed for the deployment:

| Variable | Default | Purpose |
| --- | --- | --- |
| `LOG_SERVICE` | `backend` | Stable service label such as `backend`, `monitor-worker`, `email-worker`, or `scheduler` |
| `SESSION_TTL_SECONDS` | `3600` | Idle session lifetime |
| `SESSION_ABSOLUTE_TTL_SECONDS` | `86400` | Absolute session lifetime |
| `SESSION_COOKIE_SECURE` | Forced `true` | Secure-cookie override; production cannot disable it |
| `SESSION_COOKIE_SAMESITE` | `lax` | `lax`, `strict`, or `none`; `none` requires secure cookies |
| `AUTH_ALLOW_MISSING_ORIGIN` | `false` | Must remain `false` in production |
| `AUTH_TRUSTED_PROXY_ADDRESSES` | Empty | Comma-separated trusted proxy IPs/CIDRs supplied by the selected provider |
| `AUTH_LOGIN_RATE_LIMIT_ATTEMPTS` | `5` | Login attempts per window |
| `AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS` | `60` | Login window |
| `AUTH_REGISTRATION_RATE_LIMIT_ATTEMPTS` | `3` | Registration attempts per window |
| `AUTH_REGISTRATION_RATE_LIMIT_WINDOW_SECONDS` | `60` | Registration window |
| `SCHEDULER_DISPATCH_INTERVAL_SECONDS` | `30` | Celery beat dispatch interval |
| `MONITOR_MAX_RESPONSE_BYTES` | `1048576` | Maximum monitor response body |
| `EMAIL_TIMEOUT_SECONDS` | `10` | SMTP timeout |

`DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USER`,
`DATABASE_PASSWORD`, `REDIS_HOST`, `REDIS_PORT`, and `REDIS_DB` are
development conveniences used only to construct fallback URLs. Production
requires the complete URL variables above and should not configure the
fallback fields separately.

## Frontend configuration

| Variable | Stage | Classification | Purpose |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | Image build | Public | Browser-visible HTTPS API URL; credentials are forbidden |
| `INTERNAL_API_BASE_URL` | Runtime | Non-secret, server-only | Absolute internal or public API URL used by the Next.js proxy |
| `SESSION_COOKIE_NAME` | Runtime | Non-secret, server-only | Must exactly match the backend cookie name |

The production image build fails unless `NEXT_PUBLIC_API_BASE_URL` is an
absolute HTTPS URL. The production server exits before listening if either
runtime variable is missing or invalid. `NODE_ENV`, `HOSTNAME`, `PORT`, and
`NEXT_TELEMETRY_DISABLED` are set by the image. `NEXT_DIST_DIR` and the E2E
variables are build/test tooling, not deployment settings.

## Platform secret setup

Once a provider is deliberately selected:

1. Create separate secret records for each environment; never reuse
   development or staging credentials in production.
2. Grant read access only to the services that need each secret. The frontend
   receives no database, Redis, authentication, SMTP, or registry credential.
3. Inject secret references as environment variables. Do not copy resolved
   values into deployment manifests.
4. Keep `FRONTEND_ORIGIN`, `NEXT_PUBLIC_API_BASE_URL`, and
   `INTERNAL_API_BASE_URL` aligned with the deployed frontend/API locations.
5. Record the owner, creation date, expiry policy, and last rotation in the
   provider's audit metadata without recording the secret value.
6. Start each service once with a deliberately omitted required variable and
   confirm its platform logs show the variable name but no sensitive value.

## Rotation runbook

- **Authentication digest secret:** generate a new independent random value,
  update all backend services in one release, and restart them together.
  Existing sessions remain valid, but current rate-limit counters reset because
  their privacy-preserving keys change.
- **Database credential:** create a new database credential first, update
  `DATABASE_URL` for migration/API/worker/scheduler services, verify readiness
  and a migration inspection, then revoke the old credential.
- **Redis credential:** plan a short maintenance/drain window if the provider
  cannot overlap credentials. Update `REDIS_URL`, `CELERY_BROKER_URL`, and
  `CELERY_RESULT_BACKEND` atomically, restart all backend services, verify
  sessions and queues, then revoke the old credential.
- **SMTP credential:** issue a new provider token, update `EMAIL_USERNAME` and
  `EMAIL_PASSWORD` together, restart the notification worker, deliver a test
  notification, then revoke the previous token.

For every rotation, keep the old credential active until health/readiness and
the relevant functional check pass. If validation fails, restore the previous
secret reference and redeploy; do not paste either credential into logs or
incident tickets.
