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

## Configuration

- `SESSION_COOKIE_NAME` defaults to `amp_session`.
- `SESSION_TTL_SECONDS` defaults to `3600` and must be positive.
- `SESSION_COOKIE_SAMESITE` accepts `lax`, `strict`, or `none`.
- `SESSION_COOKIE_SECURE` may enable secure cookies outside production; production
  enables them regardless of this value.
- `SameSite=None` is rejected unless secure cookies are enabled.
