# API error contract

All mapped API failures return `application/json` with one top-level `error` object:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "fields": [
      {"field": "email", "message": "Enter a valid email address."}
    ]
  }
}
```

`code` and `message` are always present. `fields` appears only for safe field-level
errors. Rate-limit responses also include a bounded `retry_after_seconds` value
when a numeric `Retry-After` header is available. Validation, authentication,
authorization, not-found, conflict, rate-limit, service, and internal failures use
this envelope. Internal exception text, stack traces, SQL, filesystem, provider,
network, and environment details are never returned.

Foreign user-owned resources follow the same `404` response as missing resources.
