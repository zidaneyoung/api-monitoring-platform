# Date and time handling

The application treats every persisted timestamp as an instant in UTC. PostgreSQL
connections set the session timezone to `UTC`, and every timestamp column uses
`timestamp with time zone`. Existing migrations already use timezone-aware columns,
so no data migration is required.

Backend clocks produce aware UTC datetimes. Internal boundaries accept aware values
with any offset and normalize them to UTC; naive datetimes are rejected because their
meaning is ambiguous. API responses serialize timestamps as RFC 3339 UTC strings with
a `Z` suffix, for example `2026-07-22T14:30:00Z`.

The frontend accepts only API timestamps that include `Z` or an explicit numeric
offset. It preserves the original API value and converts a parsed copy to the viewer's
local timezone only when rendering. Incident durations are calculated on the backend
from persisted instants, never from browser time.
