export type IncidentStatus = "open" | "acknowledged" | "resolved"
export type IncidentSection = "open" | "resolved"

export type IncidentCheckDto = {
  id: string
  started_at: string
  completed_at: string
  success: boolean
  response_time_ms: number | null
  http_status_code: number | null
  error_category: string | null
  error_message: string | null
}

export type IncidentEventDto = {
  id: string
  sequence_number: number
  event_type: string
  occurred_at: string
  message: string | null
}

export type IncidentListItemDto = {
  id: string
  monitor_id: string
  monitor_name: string
  status: IncidentStatus
  opened_at: string
  resolved_at: string | null
  duration_seconds: number
  cause_category: string | null
  cause_message: string | null
}

export type IncidentListDto = {
  items: IncidentListItemDto[]
  page: number
  page_size: number
  total: number
  pages: number
}

export type IncidentDto = IncidentListItemDto & {
  detected_at: string
  monitor: { id: string; name: string }
  triggering_check: IncidentCheckDto | null
  recovery_check: IncidentCheckDto | null
  events: IncidentEventDto[]
}

export type IncidentOutcome<T> =
  | { type: "success"; data: T }
  | { type: "not_found" }
  | { type: "unauthenticated" }
  | { type: "unavailable" }
  | { type: "timeout" }
  | { type: "network_error" }
  | { type: "cancelled" }
  | { type: "unexpected_response" }

export type IncidentReadOptions = {
  signal?: AbortSignal
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
const INCIDENT_REQUEST_TIMEOUT_MS = 10_000

function responseFailure(status: number): IncidentOutcome<never> {
  if (status === 401) return { type: "unauthenticated" }
  if (status === 404) return { type: "not_found" }
  if (status === 502 || status === 503 || status === 504) return { type: "unavailable" }
  return { type: "unexpected_response" }
}

function requestFailure(error: unknown, signal?: AbortSignal): IncidentOutcome<never> {
  if (signal?.aborted) return { type: "cancelled" }
  if (
    error instanceof DOMException
    && (error.name === "AbortError" || error.name === "TimeoutError")
  ) {
    return { type: "timeout" }
  }
  return { type: "network_error" }
}

function requestSignal(signal?: AbortSignal): AbortSignal {
  const timeoutSignal = AbortSignal.timeout(INCIDENT_REQUEST_TIMEOUT_MS)
  return signal ? AbortSignal.any([signal, timeoutSignal]) : timeoutSignal
}

function isIncidentStatus(value: unknown): value is IncidentStatus {
  return value === "open" || value === "acknowledged" || value === "resolved"
}

function isIncidentListItem(value: unknown): value is IncidentListItemDto {
  if (!value || typeof value !== "object") return false
  const item = value as Partial<IncidentListItemDto>
  return typeof item.id === "string"
    && typeof item.monitor_id === "string"
    && typeof item.monitor_name === "string"
    && isIncidentStatus(item.status)
    && typeof item.opened_at === "string"
    && (typeof item.resolved_at === "string" || item.resolved_at === null)
    && typeof item.duration_seconds === "number"
    && item.duration_seconds >= 0
}

function isIncidentList(value: unknown): value is IncidentListDto {
  if (!value || typeof value !== "object") return false
  const page = value as Partial<IncidentListDto>
  return Array.isArray(page.items)
    && page.items.every(isIncidentListItem)
    && typeof page.page === "number"
    && typeof page.page_size === "number"
    && typeof page.total === "number"
    && typeof page.pages === "number"
}

function isIncidentDetail(value: unknown): value is IncidentDto {
  if (!isIncidentListItem(value)) return false
  const incident = value as Partial<IncidentDto>
  return typeof incident.detected_at === "string"
    && Boolean(incident.monitor)
    && typeof incident.monitor?.id === "string"
    && typeof incident.monitor?.name === "string"
    && (incident.triggering_check === null || typeof incident.triggering_check === "object")
    && (incident.recovery_check === null || typeof incident.recovery_check === "object")
    && Array.isArray(incident.events)
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    return null
  }
}

async function readWithOneRetry<T>(
  request: () => Promise<IncidentOutcome<T>>,
  signal?: AbortSignal,
): Promise<IncidentOutcome<T>> {
  const first = await request()
  if (signal?.aborted) return { type: "cancelled" }
  if (first.type !== "network_error" && first.type !== "timeout" && first.type !== "unavailable") {
    return first
  }
  return request()
}

export async function listIncidents(
  section: IncidentSection,
  page: number,
  pageSize: number,
  options: IncidentReadOptions = {},
): Promise<IncidentOutcome<IncidentListDto>> {
  const query = new URLSearchParams({
    status: section,
    page: String(page),
    page_size: String(pageSize),
  })
  return readWithOneRetry(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/incidents?${query}`, {
        method: "GET",
        credentials: "include",
        cache: "no-store",
        signal: requestSignal(options.signal),
      })
      if (!response.ok) return responseFailure(response.status)
      const value = await readJson(response)
      return isIncidentList(value)
        ? { type: "success", data: value }
        : { type: "unexpected_response" }
    } catch (error) {
      return requestFailure(error, options.signal)
    }
  }, options.signal)
}

export async function getIncident(
  incidentId: string,
  options: IncidentReadOptions = {},
): Promise<IncidentOutcome<IncidentDto>> {
  return readWithOneRetry(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/incidents/${encodeURIComponent(incidentId)}`, {
        method: "GET",
        credentials: "include",
        cache: "no-store",
        signal: requestSignal(options.signal),
      })
      if (!response.ok) return responseFailure(response.status)
      const value = await readJson(response)
      return isIncidentDetail(value)
        ? { type: "success", data: value }
        : { type: "unexpected_response" }
    } catch (error) {
      return requestFailure(error, options.signal)
    }
  }, options.signal)
}

export function incidentSection(status: IncidentStatus): IncidentSection {
  return status === "resolved" ? "resolved" : "open"
}

export function formatIncidentDuration(seconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(seconds))
  const days = Math.floor(safeSeconds / 86_400)
  const hours = Math.floor((safeSeconds % 86_400) / 3_600)
  const minutes = Math.floor((safeSeconds % 3_600) / 60)
  const remainder = safeSeconds % 60
  const parts = [
    days > 0 ? `${days}d` : null,
    hours > 0 ? `${hours}h` : null,
    minutes > 0 ? `${minutes}m` : null,
    days === 0 && hours === 0 ? `${remainder}s` : null,
  ].filter((part): part is string => part !== null)
  return parts.join(" ")
}
