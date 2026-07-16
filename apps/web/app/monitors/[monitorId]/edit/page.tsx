import { MonitorEdit } from "./monitor-edit"


export default async function EditMonitorPage({
  params,
}: {
  params: Promise<{ monitorId: string }>
}) {
  const { monitorId } = await params
  return <MonitorEdit monitorId={monitorId} />
}
