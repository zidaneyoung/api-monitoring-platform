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
  latest_error_category: string | null
}

export type MonitorCreatePayload = Omit<
  MonitorDto,
  | "id"
  | "status"
  | "next_check_at"
  | "last_checked_at"
  | "latest_response_time_ms"
  | "latest_status_code"
  | "latest_error_category"
>
export type MonitorUpdatePayload = MonitorCreatePayload

export type MonitorListDto = {
  items: MonitorDto[]
  page: number
  page_size: number
  total: number
  pages: number
}

export type MonitorSummaryDto = {
  total: number
  up: number
  down: number
  paused: number
  unknown: number
}

export type MonitorCheckDto = {
  id: string
  success: boolean
  completed_at: string
  response_time_ms: number | null
  http_status_code: number | null
  error_category: string | null
}

export type MonitorCheckListDto = {
  items: MonitorCheckDto[]
  page: number
  page_size: number
  total: number
  pages: number
}

export type MonitorResponseTimePointDto = {
  completed_at: string
  response_time_ms: number | null
  success: boolean
}

export type MonitorResponseTimeSeriesDto = {
  range: "24h"
  started_at: string
  ended_at: string
  points: MonitorResponseTimePointDto[]
}

export type MonitorField = keyof MonitorCreatePayload | "form"

export type MonitorError = {
  field: MonitorField
  message: string
}

export type MonitorOutcome<T> =
  | { type: "success"; data: T }
  | { type: "validation"; errors: MonitorError[] }
  | { type: "not_found" }
  | { type: "unauthenticated" }
  | { type: "forbidden" }
  | { type: "conflict" }
  | { type: "rate_limited" }
  | { type: "internal_error" }
  | { type: "unavailable" }
  | { type: "timeout" }
  | { type: "network_error" }
  | { type: "cancelled" }
  | { type: "unexpected_response" }

export type MonitorReadOptions = {
  signal?: AbortSignal
}

type ErrorPayload = {
  errors?: Array<{ field?: string; message?: string }>
  detail?: { code?: string; message?: string }
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
    if (payload.detail?.code === "unsafe_monitor_destination") {
      return [{
        field: "url",
        message: payload.detail.message || "Monitor URL must resolve to a public destination.",
      }]
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

async function readMonitorSummary(response: Response): Promise<MonitorSummaryDto | null> {
  try {
    const value = await response.json() as Partial<MonitorSummaryDto>
    const counts = [value.up, value.down, value.paused, value.unknown]
    return typeof value.total === "number"
      && counts.every((count) => typeof count === "number" && count >= 0)
      && value.total === counts.reduce<number>((total, count) => total + (count ?? 0), 0)
      ? value as MonitorSummaryDto
      : null
  } catch {
    return null
  }
}

async function readMonitorCheckList(response: Response): Promise<MonitorCheckListDto | null> {
  try {
    const value = await response.json() as Partial<MonitorCheckListDto>
    return Array.isArray(value.items)
      && value.items.every((item) => (
        typeof item?.id === "string"
        && typeof item.success === "boolean"
        && typeof item.completed_at === "string"
        && (typeof item.response_time_ms === "number" || item.response_time_ms === null)
        && (typeof item.http_status_code === "number" || item.http_status_code === null)
        && (typeof item.error_category === "string" || item.error_category === null)
      ))
      && typeof value.page === "number"
      && typeof value.page_size === "number"
      && typeof value.total === "number"
      && typeof value.pages === "number"
      ? value as MonitorCheckListDto
      : null
  } catch {
    return null
  }
}

async function readMonitorResponseTimeSeries(response: Response): Promise<MonitorResponseTimeSeriesDto | null> {
  try {
    const value = await response.json() as Partial<MonitorResponseTimeSeriesDto>
    return value.range === "24h"
      && typeof value.started_at === "string"
      && typeof value.ended_at === "string"
      && Array.isArray(value.points)
      && value.points.every((point) => (
        typeof point?.completed_at === "string"
        && (typeof point.response_time_ms === "number" || point.response_time_ms === null)
        && typeof point.success === "boolean"
      ))
      ? value as MonitorResponseTimeSeriesDto
      : null
  } catch {
    return null
  }
}

function requestSignal(signal?: AbortSignal): AbortSignal {
  const timeoutSignal = AbortSignal.timeout(MONITOR_REQUEST_TIMEOUT_MS)
  return signal ? AbortSignal.any([signal, timeoutSignal]) : timeoutSignal
}

function requestFailure(error: unknown, signal?: AbortSignal): MonitorOutcome<never> {
  if (signal?.aborted) return { type: "cancelled" }
  if (
    error instanceof DOMException
    && (error.name === "AbortError" || error.name === "TimeoutError")
  ) {
    return { type: "timeout" }
  }
  return { type: "network_error" }
}

function responseFailure(status: number): MonitorOutcome<never> {
  if (status === 401) return { type: "unauthenticated" }
  if (status === 403) return { type: "forbidden" }
  if (status === 404) return { type: "not_found" }
  if (status === 409) return { type: "conflict" }
  if (status === 429) return { type: "rate_limited" }
  if (status === 502 || status === 503 || status === 504) return { type: "unavailable" }
  if (status >= 500) return { type: "internal_error" }
  return { type: "unexpected_response" }
}

function isTransientReadFailure(outcome: MonitorOutcome<unknown>): boolean {
  return outcome.type === "network_error"
    || outcome.type === "timeout"
    || outcome.type === "unavailable"
}

async function readWithOneRetry<T>(
  request: () => Promise<MonitorOutcome<T>>,
  signal?: AbortSignal,
): Promise<MonitorOutcome<T>> {
  const first = await request()
  if (signal?.aborted) return { type: "cancelled" }
  if (!isTransientReadFailure(first)) return first
  return request()
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
    return responseFailure(response.status)
  } catch (error) {
    return requestFailure(error)
  }
}

export async function updateMonitor(
  monitorId: string,
  payload: MonitorUpdatePayload,
): Promise<MonitorOutcome<MonitorDto>> {
  try {
    const response = await fetch(`${API_BASE_URL}/monitors/${encodeURIComponent(monitorId)}`, {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(MONITOR_REQUEST_TIMEOUT_MS),
    })

    if (response.ok) {
      const monitor = await readMonitor(response)
      return monitor
        ? { type: "success", data: monitor }
        : { type: "unexpected_response" }
    }
    if (response.status === 422) {
      return { type: "validation", errors: await readValidationErrors(response) }
    }
    return responseFailure(response.status)
  } catch (error) {
    return requestFailure(error)
  }
}

export async function listMonitors(
  page: number,
  pageSize: number,
  options: MonitorReadOptions = {},
): Promise<MonitorOutcome<MonitorListDto>> {
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  return readWithOneRetry(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/monitors?${query}`, {
        method: "GET",
        credentials: "include",
        cache: "no-store",
        signal: requestSignal(options.signal),
      })

      if (response.ok) {
        const monitors = await readMonitorList(response)
        return monitors
          ? { type: "success", data: monitors }
          : { type: "unexpected_response" }
      }
      return responseFailure(response.status)
    } catch (error) {
      return requestFailure(error, options.signal)
    }
  }, options.signal)
}

export async function getMonitorSummary(
  options: MonitorReadOptions = {},
): Promise<MonitorOutcome<MonitorSummaryDto>> {
  return readWithOneRetry(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/monitors/summary`, {
        method: "GET",
        credentials: "include",
        cache: "no-store",
        signal: requestSignal(options.signal),
      })

      if (response.ok) {
        const summary = await readMonitorSummary(response)
        return summary
          ? { type: "success", data: summary }
          : { type: "unexpected_response" }
      }
      return responseFailure(response.status)
    } catch (error) {
      return requestFailure(error, options.signal)
    }
  }, options.signal)
}

export async function listRecentChecks(
  monitorId: string,
  page: number,
  pageSize: number,
  options: MonitorReadOptions = {},
): Promise<MonitorOutcome<MonitorCheckListDto>> {
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  return readWithOneRetry(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/monitors/${encodeURIComponent(monitorId)}/checks?${query}`, {
        method: "GET",
        credentials: "include",
        cache: "no-store",
        signal: requestSignal(options.signal),
      })
      if (response.ok) {
        const checks = await readMonitorCheckList(response)
        return checks
          ? { type: "success", data: checks }
          : { type: "unexpected_response" }
      }
      return responseFailure(response.status)
    } catch (error) {
      return requestFailure(error, options.signal)
    }
  }, options.signal)
}

export async function getMonitorResponseTimes(
  monitorId: string,
  options: MonitorReadOptions = {},
): Promise<MonitorOutcome<MonitorResponseTimeSeriesDto>> {
  return readWithOneRetry(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/monitors/${encodeURIComponent(monitorId)}/response-times?range=24h`, {
        method: "GET",
        credentials: "include",
        cache: "no-store",
        signal: requestSignal(options.signal),
      })
      if (response.ok) {
        const series = await readMonitorResponseTimeSeries(response)
        return series
          ? { type: "success", data: series }
          : { type: "unexpected_response" }
      }
      return responseFailure(response.status)
    } catch (error) {
      return requestFailure(error, options.signal)
    }
  }, options.signal)
}

export async function getMonitor(
  monitorId: string,
  options: MonitorReadOptions = {},
): Promise<MonitorOutcome<MonitorDto>> {
  return readWithOneRetry(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/monitors/${encodeURIComponent(monitorId)}`, {
        method: "GET",
        credentials: "include",
        cache: "no-store",
        signal: requestSignal(options.signal),
      })

      if (response.ok) {
        const monitor = await readMonitor(response)
        return monitor
          ? { type: "success", data: monitor }
          : { type: "unexpected_response" }
      }
      return responseFailure(response.status)
    } catch (error) {
      return requestFailure(error, options.signal)
    }
  }, options.signal)
}

export async function pauseMonitor(
  monitorId: string,
): Promise<MonitorOutcome<MonitorDto>> {
  try {
    const response = await fetch(`${API_BASE_URL}/monitors/${encodeURIComponent(monitorId)}/pause`, {
      method: "POST",
      credentials: "include",
      signal: AbortSignal.timeout(MONITOR_REQUEST_TIMEOUT_MS),
    })

    if (response.ok) {
      const monitor = await readMonitor(response)
      return monitor
        ? { type: "success", data: monitor }
        : { type: "unexpected_response" }
    }
    return responseFailure(response.status)
  } catch (error) {
    return requestFailure(error)
  }
}

export async function resumeMonitor(
  monitorId: string,
): Promise<MonitorOutcome<MonitorDto>> {
  try {
    const response = await fetch(`${API_BASE_URL}/monitors/${encodeURIComponent(monitorId)}/resume`, {
      method: "POST",
      credentials: "include",
      signal: AbortSignal.timeout(MONITOR_REQUEST_TIMEOUT_MS),
    })

    if (response.ok) {
      const monitor = await readMonitor(response)
      return monitor
        ? { type: "success", data: monitor }
        : { type: "unexpected_response" }
    }
    return responseFailure(response.status)
  } catch (error) {
    return requestFailure(error)
  }
}

export async function deleteMonitor(
  monitorId: string,
): Promise<MonitorOutcome<null>> {
  try {
    const response = await fetch(`${API_BASE_URL}/monitors/${encodeURIComponent(monitorId)}`, {
      method: "DELETE",
      credentials: "include",
      signal: AbortSignal.timeout(MONITOR_REQUEST_TIMEOUT_MS),
    })

    if (response.status === 204) return { type: "success", data: null }
    return responseFailure(response.status)
  } catch (error) {
    return requestFailure(error)
  }
}
