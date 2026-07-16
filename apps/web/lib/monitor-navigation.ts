export const DEFAULT_MONITOR_PAGE = 1
export const DEFAULT_MONITOR_PAGE_SIZE = 10
export const MONITOR_PAGE_SIZES = [5, 10, 25] as const

type MonitorListSearch = {
  page?: string | string[]
  page_size?: string | string[]
}

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

function positiveInteger(value: string | undefined, fallback: number): number {
  if (!value || !/^\d+$/.test(value)) return fallback
  const parsed = Number(value)
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : fallback
}

export function parseMonitorListSearch(search: MonitorListSearch): {
  page: number
  pageSize: number
} {
  const page = positiveInteger(first(search.page), DEFAULT_MONITOR_PAGE)
  const requestedPageSize = positiveInteger(first(search.page_size), DEFAULT_MONITOR_PAGE_SIZE)
  const pageSize = MONITOR_PAGE_SIZES.includes(requestedPageSize as (typeof MONITOR_PAGE_SIZES)[number])
    ? requestedPageSize
    : DEFAULT_MONITOR_PAGE_SIZE

  return { page, pageSize }
}

export function monitorListHref(page = DEFAULT_MONITOR_PAGE, pageSize = DEFAULT_MONITOR_PAGE_SIZE): string {
  return `/monitors?page=${page}&page_size=${pageSize}`
}

export function safeMonitorReturnHref(value: string | string[] | undefined): string {
  const candidate = first(value)
  if (!candidate) return monitorListHref()

  try {
    const parsed = new URL(candidate, "https://monitoring.local")
    if (parsed.origin !== "https://monitoring.local" || parsed.pathname !== "/monitors") {
      return monitorListHref()
    }
    const search = parseMonitorListSearch({
      page: parsed.searchParams.get("page") ?? undefined,
      page_size: parsed.searchParams.get("page_size") ?? undefined,
    })
    return monitorListHref(search.page, search.pageSize)
  } catch {
    return monitorListHref()
  }
}

export function monitorDetailsHref(monitorId: string, returnHref: string): string {
  return `/monitors/${encodeURIComponent(monitorId)}?return_to=${encodeURIComponent(returnHref)}`
}

export function monitorEditHref(monitorId: string, returnHref: string): string {
  return `/monitors/${encodeURIComponent(monitorId)}/edit?return_to=${encodeURIComponent(returnHref)}`
}
