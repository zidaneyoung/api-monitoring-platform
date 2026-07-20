# Email delivery policy

Email delivery runs only on the dedicated Celery `email` queue. Monitor checks and
incident transactions create durable delivery rows and enqueue work after commit;
SMTP calls never run in those transactions.

## Failure classification and retries

- Network, timeout, and other `OSError` failures are temporary.
- SMTP 4xx responses are temporary. SMTP 421 is recorded as rate limiting and uses
  the same bounded retry schedule.
- SMTP 5xx responses and other SMTP rejections are permanent.
- Retry delay is `60 * 2^(attempt_count - 1)` seconds, capped at 3600 seconds.
- Maximum attempts are 5, including the first attempt.
- Temporary failures reuse the same delivery row, set `retrying`, persist
  `next_retry_at`, and schedule the same delivery ID with a Celery countdown.
- Permanent failures stop immediately in `failed`.
- A temporary failure on attempt 5 ends in `failed` with `attempts_exhausted`.

Stored error codes and messages are fixed safe categories. SMTP response bodies,
credentials, and exception text are not persisted or logged.

## Deduplication, claiming, and crash behavior

- The database unique constraint on `deduplication_key` prevents multiple delivery
  rows for one event, channel, and destination.
- A PostgreSQL conditional update atomically changes one due `pending` or `retrying`
  row to `sending`. Only the worker receiving the returned row may call SMTP.
- Celery acknowledges email tasks late. Redelivery before the database claim can be
  claimed normally; redelivery after a claim sees `sending` and does not send again.
- A crash before the database claim leaves `pending`/`retrying` and can be redelivered.
- A crash after the claim but before SMTP, during SMTP, or after SMTP handoff but
  before `delivered` leaves the row in `sending` with its attempt timestamp. This is
  an intentionally conservative, ambiguous outcome requiring reconciliation; it is
  not retried automatically because SMTP handoff cannot provide exactly-once delivery.
- `delivered` and `failed` are terminal and are never claimed again.

This design prevents concurrent duplicate sends and prefers avoiding duplicates in
the SMTP ambiguity window. It does not claim exactly-once external delivery.
