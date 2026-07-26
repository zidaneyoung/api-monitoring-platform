# Production database migrations

Production releases use the backend image's dedicated migration command:

```text
python -m app.production_migrations upgrade
```

The command reads `DATABASE_URL` through the validated production
configuration, acquires a stable PostgreSQL advisory lock, applies every
Alembic migration through `head`, and verifies the database revision before
returning success. It never accepts a connection URL on the command line and
does not print credentials.

If another process holds the migration lock, the command fails immediately
with exit code `75`. Any configuration, connection, migration, or revision
verification error exits with code `1` and a sanitized message. A deployment
orchestrator must treat every non-zero exit as a hard release failure.

## Release order

The selected deployment provider should implement one release job with this
order:

1. Finish automated tests and production-image builds for one immutable commit
   SHA.
2. Create and verify the pre-migration database backup.
3. Start exactly one one-off container from that backend image with the same
   production configuration as the application.
4. Run `python -m app.production_migrations upgrade` and wait for exit code
   `0`.
5. Run `python -m app.production_migrations current` in the same protected
   environment and retain its non-sensitive revision output as release
   evidence.
6. Only then start or replace API, worker, notification-worker, and scheduler
   instances.
7. Run database/Redis readiness and the post-deployment smoke test.

Do not put the migration command in every application replica's startup
command. The advisory lock is a defense-in-depth concurrency guard, not a
replacement for a single provider release job. Application rollout must have
an explicit success dependency on that job so incompatible code never starts
after a failed migration.

No deployment provider is configured in this repository, so the provider
release hook/job is an external prerequisite. The command, lock, exit
contract, image entrypoint, and production-like validation are
provider-independent.

## Revision inspection

The read-only command:

```text
python -m app.production_migrations current
```

prints `none` for a clean database or the sorted contents of Alembic's version
table. Compare that output with the migration head in the released image. It
uses the secret-injected `DATABASE_URL`; never pass or paste that URL into
release commands or tickets.

## Backup procedure

Before every release containing a schema change:

1. Use the database provider's consistent snapshot feature or a version-matched
   `pg_dump` executed from a protected job.
2. Name the backup with environment, UTC timestamp, and release commit SHA,
   without putting credentials in the name or logs.
3. Verify the backup reports success and falls within the retention policy.
4. Periodically restore a backup into an isolated non-production database and
   run `current`, readiness, and smoke checks. A backup is not considered
   verified until a restore has succeeded.

The database credential used for backup should be a scoped platform secret.
It must not be embedded in a manifest or passed as a visible command argument.

## Rollback and recovery

Prefer forward-compatible expand/migrate/contract changes so an application
rollback can run against the upgraded schema. Before merging a new migration,
review its `downgrade()` implementation, data-loss risk, lock duration, and
compatibility with the previously deployed application.

On release failure:

- Stop the application rollout immediately.
- If the migration transaction rolled back cleanly, inspect the revision and
  correct or revert the release code.
- Use `alembic downgrade` only after a human reviews that exact migration's
  downgrade path and confirms it preserves required data.
- If a migration committed destructive or irreversible changes, stop writes
  and follow the provider's documented restore procedure using the verified
  pre-migration backup. Restoration is intentionally not automated here.
- After any downgrade or restore, run `current`, readiness, and the complete
  smoke test before reopening traffic.

## Production-like validation

Run the dedicated isolated PostgreSQL suite from the repository root:

```powershell
./scripts/run-production-migration-tests.ps1
```

It starts a disposable PostgreSQL database and verifies a clean upgrade, a
second upgrade against an already migrated database, current-revision
inspection, advisory-lock exclusion, sanitized output, and a controlled
connection failure. The `Tests` GitHub Actions workflow runs the same command.
