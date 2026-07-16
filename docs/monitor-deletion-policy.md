# Monitor deletion policy

Monitor deletion is permanent hard deletion.

The authenticated `DELETE /monitors/{monitor_id}` endpoint deletes only a monitor owned by the current user. The existing PostgreSQL foreign keys use `ON DELETE CASCADE`, so the same transaction also deletes that monitor's scheduled runs, checks, incidents, incident events, and incident notification-delivery records. This keeps the current schema internally consistent; this workflow does not retain detached or anonymized history.

After commit, the monitor is absent from active-list and scheduler queries. Any already queued worker must reload the monitor by ID and call the shared current-state guard before making a request. A missing monitor fails that guard, so deleted monitors cannot be checked.

The operation is idempotent in state: after the first successful `204 No Content`, later requests make no further change and receive the same ownership-safe `404 Monitor not found` response used for missing and foreign monitors. Restoration and bulk deletion are not supported.
