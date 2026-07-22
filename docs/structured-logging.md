# Structured logging

Backend, scheduler, monitor-worker, and email-worker application events use one
JSON format. Every event includes a UTC timestamp, level, service, environment,
event name, and safe message. Context fields add request and correlation IDs or
persisted resource IDs only when they belong to the logical operation.

API clients may send `X-Request-ID` and `X-Correlation-ID` values containing 1–128
letters, digits, dots, underscores, colons, or hyphens. Invalid values are replaced
with generated UUIDs. Both identifiers are returned in response headers and carried
through request logs. Worker tasks bind their durable run or delivery ID as the
correlation ID.

The formatter recursively redacts sensitive key variants, request and response
bodies, provider error details, credentials, authorization and cookie values, API
keys, tokens, and secrets. URLs retain only scheme, host, and port followed by a
`[redacted]` marker; credentials, paths, and query strings are omitted. Application
event calls contain no raw bodies, headers, destination URLs, or provider exception
messages. Logging and formatting failures are contained so they cannot interrupt API,
scheduler, monitoring, incident, or notification work.
