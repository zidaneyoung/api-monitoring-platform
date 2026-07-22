export type ApiFieldError = {
  field: string
  message: string
}

export type ApiError = {
  code: string
  message: string
  fields: ApiFieldError[]
  retryAfterSeconds?: number
}

export async function readApiError(response: Response): Promise<ApiError | null> {
  try {
    const payload = await response.json() as unknown
    if (!payload || typeof payload !== "object" || !("error" in payload)) return null

    const error = (payload as { error?: unknown }).error
    if (!error || typeof error !== "object") return null
    const value = error as Record<string, unknown>
    if (typeof value.code !== "string" || typeof value.message !== "string") return null

    const fields = Array.isArray(value.fields)
      ? value.fields.slice(0, 20).flatMap((field): ApiFieldError[] => {
        if (!field || typeof field !== "object") return []
        const candidate = field as Record<string, unknown>
        return typeof candidate.field === "string" && typeof candidate.message === "string"
          ? [{ field: candidate.field, message: candidate.message }]
          : []
      })
      : []
    const retryAfterSeconds = typeof value.retry_after_seconds === "number"
      && Number.isFinite(value.retry_after_seconds)
      && value.retry_after_seconds >= 0
      ? Math.min(86_400, Math.ceil(value.retry_after_seconds))
      : undefined

    return {
      code: value.code,
      message: value.message,
      fields,
      ...(retryAfterSeconds === undefined ? {} : { retryAfterSeconds }),
    }
  } catch {
    return null
  }
}
