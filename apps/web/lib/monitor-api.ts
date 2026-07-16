export type MonitorStatus = "unknown" | "up" | "down" | "paused"
export type MonitorHttpMethod = "GET" | "HEAD"

export type MonitorDto = {
  id: string
  name: string
  url: string
  http_method: MonitorHttpMethod
  interval_seconds: number
  timeout_seconds: number
  expected_status_min: number
  expected_status_max: number
  failure_threshold: number
  recovery_threshold: number
  status: MonitorStatus
  next_check_at: string | null
  last_checked_at: string | null
  latest_response_time_ms: number | null
  latest_status_code: number | null
}

export type MonitorCreatePayload = Omit<
  MonitorDto,
  | "id"
  | "status"
  | "next_check_at"
  | "last_checked_at"
  | "latest_response_time_ms"
  | "latest_status_code"
>

export type MonitorListDto = {
  items: MonitorDto[]
  page: number
  page_size: number
  total: number
  pages: number
}

export type MonitorField = keyof MonitorCreatePayload | "form"

export type MonitorError = {
  field: MonitorField
  message: string
}

export type MonitorOutcome<T> =
  | { type: "success"; data: T }
  | { type: "validation"; errors: MonitorError[] }
  | { type: "unauthenticated" }
  | { type: "unavailable" }
  | { type: "timeout" }
  | { type: "network_error" }
  | { type: "unexpected_response" }

type ErrorPayload = {
  errors?: Array<{ field?: string; message?: string }>
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
const MONITOR_REQUEST_TIMEOUT_MS = 10_000
const MONITOR_FIELDS = new Set<MonitorField>([
  "name",
  "url",
  "http_method",
  "interval_seconds",
  "timeout_seconds",
  "expected_status_min",
  "expected_status_max",
  "failure_threshold",
  "recovery_threshold",
  "form",
])

function normalizeField(field: string | undefined): MonitorField {
  return field && MONITOR_FIELDS.has(field as MonitorField)
    ? field as MonitorField
    : "form"
}

async function readValidationErrors(response: Response): Promise<MonitorError[]> {
  try {
    const payload = await response.json() as ErrorPayload
    if (payload.errors?.length) {
      return payload.errors.slice(0, 10).map((error) => ({
        field: normalizeField(error.field),
        message: error.message ?? "Enter a valid value.",
      }))
    }
  } catch {
    // Malformed responses receive a controlled fallback.
  }
  return [{ field: "form", message: "Check the highlighted fields and try again." }]
}

async function readMonitor(response: Response): Promise<MonitorDto | null> {
  try {
    const value = await response.json() as Partial<MonitorDto>
    return typeof value.id === "string"
      && typeof value.name === "string"
      && typeof value.url === "string"
      ? value as MonitorDto
      : null
  } catch {
    return null
  }
}

async function readMonitorList(response: Response): Promise<MonitorListDto | null> {
  try {
    const value = await response.json() as Partial<MonitorListDto>
    return Array.isArray(value.items)
      && value.items.every((item) => (
        typeof item?.id === "string"
        && typeof item.name === "string"
        && typeof item.url === "string"
      ))
      && typeof value.page === "number"
      && typeof value.page_size === "number"
      && typeof value.total === "number"
      && typeof value.pages === "number"
      ? value as MonitorListDto
      : null
  } catch {
    return null
  }
}

function requestFailure(error: unknown): MonitorOutcome<never> {
  if (
    error instanceof DOMException
    && (error.name === "AbortError" || error.name === "TimeoutError")
  ) {
    return { type: "timeout" }
  }
  return { type: "network_error" }
}

export async function createMonitor(
  payload: MonitorCreatePayload,
): Promise<MonitorOutcome<MonitorDto>> {
  try {
    const response = await fetch(`${API_BASE_URL}/monitors`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(MONITOR_REQUEST_TIMEOUT_MS),
    })

    if (response.status === 201) {
      const monitor = await readMonitor(response)
      return monitor
        ? { type: "success", data: monitor }
        : { type: "unexpected_response" }
    }
    if (response.status === 422) {
      return { type: "validation", errors: await readValidationErrors(response) }
    }
    if (response.status === 401) return { type: "unauthenticated" }
    if (response.status === 503) return { type: "unavailable" }
    return { type: "unexpected_response" }
  } catch (error) {
    return requestFailure(error)
  }
}

export async function listMonitors(
  page: number,
  pageSize: number,
): Promise<MonitorOutcome<MonitorListDto>> {
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  try {
    const response = await fetch(`${API_BASE_URL}/monitors?${query}`, {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      signal: AbortSignal.timeout(MONITOR_REQUEST_TIMEOUT_MS),
    })

    if (response.ok) {
      const monitors = await readMonitorList(response)
      return monitors
        ? { type: "success", data: monitors }
        : { type: "unexpected_response" }
    }
    if (response.status === 401) return { type: "unauthenticated" }
    if (response.status === 503) return { type: "unavailable" }
    return { type: "unexpected_response" }
  } catch (error) {
    return requestFailure(error)
  }
}
