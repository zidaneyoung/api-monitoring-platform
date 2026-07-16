import { MonitorDetails } from "./monitor-details"


export default async function MonitorDetailsPage({
  params,
}: {
  params: Promise<{ monitorId: string }>
}) {
  const { monitorId } = await params
  return <MonitorDetails monitorId={monitorId} />
}
