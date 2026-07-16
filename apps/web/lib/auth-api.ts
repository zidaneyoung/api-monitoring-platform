export type AuthField = "email" | "password" | "form"

export type AuthError = {
  field: AuthField
  message: string
}

export type CurrentUser = {
  id: string
  email: string
}

export type AuthOutcome<T> =
  | { type: "success"; data: T }
  | { type: "validation"; errors: AuthError[] }
  | { type: "invalid_credentials" }
  | { type: "conflict"; field: "email" }
  | { type: "rate_limited"; retryAfterSeconds: number }
  | { type: "unauthenticated" }
  | { type: "unavailable" }
  | { type: "timeout" }
  | { type: "network_error" }
  | { type: "unexpected_response" }

type ErrorPayload = {
  errors?: Array<{ field?: string; message?: string }>
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
const AUTH_REQUEST_TIMEOUT_MS = 10_000
const AUTH_STATE_TIMEOUT_MS = 5_000
const DEFAULT_RETRY_AFTER_SECONDS = 60
const MAX_RETRY_AFTER_SECONDS = 3_600

function normalizeField(field: string | undefined): AuthField {
  return field === "email" || field === "password" ? field : "form"
}

async function readValidationErrors(response: Response): Promise<AuthError[]> {
  try {
    const payload = (await response.json()) as ErrorPayload
    if (payload.errors?.length) {
      return payload.errors.slice(0, 4).map((error) => ({
        field: normalizeField(error.field),
        message: error.message ?? "Enter a valid value.",
      }))
    }
  } catch {
    // Malformed validation responses receive the same controlled fallback.
  }

  return [{ field: "form", message: "Check the highlighted fields and try again." }]
}

async function readPublicUser(response: Response): Promise<CurrentUser | null> {
  try {
    const value = await response.json() as Partial<CurrentUser>
    return typeof value.id === "string" && typeof value.email === "string"
      ? { id: value.id, email: value.email }
      : null
  } catch {
    return null
  }
}

function retryAfterSeconds(response: Response): number {
  const header = response.headers.get("Retry-After")?.trim()
  if (!header) return DEFAULT_RETRY_AFTER_SECONDS

  const seconds = Number(header)
  if (Number.isFinite(seconds) && seconds >= 0) {
    return Math.min(MAX_RETRY_AFTER_SECONDS, Math.max(1, Math.ceil(seconds)))
  }

  const date = Date.parse(header)
  if (!Number.isNaN(date)) {
    const remaining = Math.ceil((date - Date.now()) / 1_000)
    return Math.min(MAX_RETRY_AFTER_SECONDS, Math.max(1, remaining))
  }

  return DEFAULT_RETRY_AFTER_SECONDS
}

function requestFailure(error: unknown): AuthOutcome<never> {
  if (
    error instanceof DOMException
    && (error.name === "AbortError" || error.name === "TimeoutError")
  ) {
    return { type: "timeout" }
  }

  return { type: "network_error" }
}

async function submitCredentials(
  endpoint: "login" | "register",
  email: string,
  password: string,
): Promise<AuthOutcome<CurrentUser>> {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/${endpoint}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
      signal: AbortSignal.timeout(AUTH_REQUEST_TIMEOUT_MS),
    })

    if (response.ok) {
      const user = await readPublicUser(response)
      return user ? { type: "success", data: user } : { type: "unexpected_response" }
    }

    if (response.status === 422) {
      return { type: "validation", errors: await readValidationErrors(response) }
    }
    if (response.status === 429) {
      return { type: "rate_limited", retryAfterSeconds: retryAfterSeconds(response) }
    }
    if (response.status === 503) return { type: "unavailable" }
    if (endpoint === "login" && response.status === 401) {
      return { type: "invalid_credentials" }
    }
    if (endpoint === "register" && response.status === 409) {
      return { type: "conflict", field: "email" }
    }

    return { type: "unexpected_response" }
  } catch (error) {
    return requestFailure(error)
  }
}

export async function registerUser(
  email: string,
  password: string,
): Promise<AuthOutcome<CurrentUser>> {
  return submitCredentials("register", email, password)
}

export async function loginUser(
  email: string,
  password: string,
): Promise<AuthOutcome<CurrentUser>> {
  return submitCredentials("login", email, password)
}

export async function getCurrentUser(): Promise<AuthOutcome<CurrentUser>> {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/me`, {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      signal: AbortSignal.timeout(AUTH_STATE_TIMEOUT_MS),
    })

    if (response.ok) {
      const user = await readPublicUser(response)
      return user ? { type: "success", data: user } : { type: "unexpected_response" }
    }
    if (response.status === 401) return { type: "unauthenticated" }
    if (response.status === 503) return { type: "unavailable" }
    return { type: "unexpected_response" }
  } catch (error) {
    return requestFailure(error)
  }
}

export async function logoutUser(): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/logout`, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
      signal: AbortSignal.timeout(AUTH_STATE_TIMEOUT_MS),
    })

    if (response.ok) return
  } catch {
    // Logout receives a richer result contract in the shell UX follow-up.
  }

  throw new Error("Unable to log out. Try again.")
}
