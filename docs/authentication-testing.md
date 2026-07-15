# Authentication test isolation

Authentication integration tests require `TEST_DATABASE_URL` and `TEST_REDIS_URL`.
Both targets must differ from the application runtime database and Redis database;
the security suite fails before writing if either target matches. Test users use
unique UUID-derived email addresses, and cleanup deletes only those users and their
hashed session keys.

The automated suite covers registration success and validation/duplicate failure,
login success and generic failure, disabled users, cookie persistence, expiration,
logout invalidation, protected current-user rejection, two independent users, and
sensitive-data exclusion. It verifies that an authenticated `/auth/me` request
always returns the session owner even when another user ID is supplied as an
unrecognized query parameter.

## Current user-owned resource scope

Order 2 exposes only the authenticated current-user read endpoint. Monitor,
incident, and notification-delivery models exist, but no read, edit, or delete API
routes for those resources exist yet. Cross-user CRUD coverage for those later
resources is therefore dependency-blocked, not silently claimed and not implemented
as part of authentication hardening. Add resource-specific isolation tests when the
corresponding APIs are introduced by later orders.
