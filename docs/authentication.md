# Authentication sessions

Authentication uses server-side, opaque sessions instead of browser-readable access
tokens.

## Lifecycle

1. Successful login creates a cryptographically random session token.
2. The browser receives the token only in the `amp_session` cookie. The cookie is
   `HttpOnly`, scoped to `/`, configured with `SameSite`, and has a one-hour
   `Max-Age` by default. Production always adds `Secure`.
3. Redis stores only a SHA-256 digest of the token in the key and maps it to the
   user ID with the same TTL as the cookie. Raw tokens, passwords, and password
   hashes are never used in Redis keys or logs.
4. `GET /auth/me` validates the cookie against Redis and the current database user.
   A valid request atomically renews the Redis TTL and returns only the user's ID
   and email. The response renews the cookie `Max-Age`, providing a sliding session.
5. Missing, tampered, expired, unknown-user, and disabled-user sessions receive a
   generic `401` response. Invalid user sessions are removed from Redis.
6. `POST /auth/logout` deletes the active Redis session and expires the browser
   cookie. Repeating logout is safe and does not affect any other user's session.
7. Once the TTL expires, Redis removes the session and the cookie can no longer
   authenticate.

Frontend requests use `credentials: "include"`. Authentication tokens are never
written to `localStorage` or `sessionStorage`. Backend authorization must use the
authenticated-session dependency; frontend route checks are only a user-experience
guard and are not an authorization boundary.

Next.js Proxy verifies the backend session before dashboard, monitor, or incident
routes render. Unauthenticated requests are redirected to login with their intended
path and query in the `next` parameter. The backend remains the authorization
boundary for every protected data operation.

## Authentication rate limits

Redis holds fixed-window counters shared by all backend instances. Login allows five
attempts per client address in 60 seconds; registration allows three. The next
request receives `429 Too Many Requests`, a generic error body, and a `Retry-After`
header. Requests are accepted again after the window expires. If Redis cannot
enforce a limit, authentication fails closed with a controlled `503` response.

Keys contain only the route scope and a SHA-256 digest of the resolved client
address. Submitted email addresses, passwords, cookies, tokens, and request bodies
are never included in rate-limit keys or logs. Untrusted forwarding headers are not
used to identify clients.

## Configuration

- `SESSION_COOKIE_NAME` defaults to `amp_session`.
- `SESSION_TTL_SECONDS` defaults to `3600` and must be positive.
- `SESSION_COOKIE_SAMESITE` accepts `lax`, `strict`, or `none`.
- `SESSION_COOKIE_SECURE` may enable secure cookies outside production; production
  enables them regardless of this value.
- `SameSite=None` is rejected unless secure cookies are enabled.
- `AUTH_LOGIN_RATE_LIMIT_ATTEMPTS` defaults to `5`.
- `AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS` defaults to `60`.
- `AUTH_REGISTRATION_RATE_LIMIT_ATTEMPTS` defaults to `3`.
- `AUTH_REGISTRATION_RATE_LIMIT_WINDOW_SECONDS` defaults to `60`.
