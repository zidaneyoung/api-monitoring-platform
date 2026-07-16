import { redirect } from "next/navigation"

import { monitorListHref, parseMonitorListSearch } from "@/lib/monitor-navigation"
import { MonitorList } from "./monitor-list"

export default async function MonitorsPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string | string[]; page_size?: string | string[] }>
}) {
  const rawSearch = await searchParams
  const { page, pageSize } = parseMonitorListSearch(rawSearch)
  const rawPage = Array.isArray(rawSearch.page) ? rawSearch.page[0] : rawSearch.page
  const rawPageSize = Array.isArray(rawSearch.page_size) ? rawSearch.page_size[0] : rawSearch.page_size

  if (rawPage !== String(page) || rawPageSize !== String(pageSize)) {
    redirect(monitorListHref(page, pageSize))
  }

  return <MonitorList initialPage={page} initialPageSize={pageSize} />
}
