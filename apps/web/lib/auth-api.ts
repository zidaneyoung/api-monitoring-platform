export type AuthField = "email" | "password" | "form"

export type AuthError = {
  field: AuthField
  message: string
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
