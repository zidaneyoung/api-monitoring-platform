import { MonitorList, type MonitorViewState } from "./monitor-list"

export default async function MonitorsPage({
  searchParams,
}: {
  searchParams: Promise<{ state?: string | string[]; q?: string | string[] }>
}) {
  const resolvedSearchParams = await searchParams
  const requestedView = Array.isArray(resolvedSearchParams.state) ? resolvedSearchParams.state[0] : resolvedSearchParams.state
  const initialQuery = Array.isArray(resolvedSearchParams.q) ? resolvedSearchParams.q[0] : resolvedSearchParams.q
  const viewState: MonitorViewState =
    requestedView === "loading" || requestedView === "empty" || requestedView === "error" ? requestedView : "list"

  return <MonitorList viewState={viewState} initialQuery={initialQuery} />
}
