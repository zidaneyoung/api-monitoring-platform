import { MonitorList, type MonitorViewState } from "./monitor-list"

export default async function MonitorsPage({
  searchParams,
}: {
  searchParams: Promise<{ state?: string }>
}) {
  const requestedView = (await searchParams).state
  const viewState: MonitorViewState =
    requestedView === "loading" || requestedView === "empty" || requestedView === "error" ? requestedView : "list"

  return <MonitorList viewState={viewState} />
}
