export type AuthField = "email" | "password" | "form"

export type AuthError = {
  field: AuthField
  message: string
}

export type CurrentUser = {
  id: string
  email: string
}

type ErrorPayload = {
  errors?: Array<{ field?: string; message?: string }>
  detail?: { field?: string; message?: string }
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

function normalizeField(field: string | undefined): AuthField {
  return field === "email" || field === "password" ? field : "form"
}

async function readErrors(response: Response): Promise<AuthError[]> {
  let payload: ErrorPayload = {}
  try {
    payload = (await response.json()) as ErrorPayload
  } catch {
    return [{ field: "form", message: "Unable to complete the request. Try again." }]
  }

  if (payload.errors?.length) {
    return payload.errors.map((error) => ({
      field: normalizeField(error.field),
      message: error.message ?? "Enter a valid value.",
    }))
  }

  if (payload.detail?.message) {
    return [{
      field: normalizeField(payload.detail.field),
      message: payload.detail.message,
    }]
  }

  return [{ field: "form", message: "Unable to complete the request. Try again." }]
}

export async function registerUser(email: string, password: string): Promise<AuthError[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })

    return response.ok ? [] : readErrors(response)
  } catch {
    return [{ field: "form", message: "Unable to reach the service. Try again." }]
  }
}

export async function loginUser(email: string, password: string): Promise<AuthError[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })

    return response.ok ? [] : readErrors(response)
  } catch {
    return [{ field: "form", message: "Unable to reach the service. Try again." }]
  }
}

export function safeAuthRedirect(destination: string | undefined): string {
  if (
    !destination
    || !destination.startsWith("/")
    || destination.startsWith("//")
    || destination.includes("\\")
    || /[\u0000-\u001f]/.test(destination)
  ) {
    return "/dashboard"
  }

  const parsed = new URL(destination, "http://app.local")
  return parsed.origin === "http://app.local"
    ? `${parsed.pathname}${parsed.search}${parsed.hash}`
    : "/dashboard"
}

export async function getCurrentUser(): Promise<CurrentUser | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/me`, {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    })

    return response.ok ? (await response.json()) as CurrentUser : null
  } catch {
    return null
  }
}

export async function logoutUser(): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/logout`, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
    })

    if (response.ok) return
  } catch {
    // The UI receives the same safe message for network and server failures.
  }

  throw new Error("Unable to log out. Try again.")
}
