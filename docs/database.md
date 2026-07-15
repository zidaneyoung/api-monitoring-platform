# Database policies

## Monitor ownership

Monitors are owned by exactly one user. Deleting a user deletes that user's monitors
and, through their foreign keys, all monitor execution history. This cascade is the
intentional account-deletion policy; monitors are not reassigned or retained as
ownerless records.

## Incident safety

Incident cause categories and messages contain only normalized, user-safe diagnostic
details. Callers must remove credentials, tokens, response bodies, and other secrets
before persisting these fields.

Notification delivery rows store provider message identifiers and normalized error
codes/messages only. Raw provider responses, API keys, and provider credentials must
not be stored in notification delivery fields.
