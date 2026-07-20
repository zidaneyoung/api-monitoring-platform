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
