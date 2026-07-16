import { MonitorDetails } from "./monitor-details"
import { safeMonitorReturnHref } from "@/lib/monitor-navigation"


export default async function MonitorDetailsPage({
  params,
  searchParams,
}: {
  params: Promise<{ monitorId: string }>
  searchParams: Promise<{ return_to?: string | string[] }>
}) {
  const { monitorId } = await params
  const returnHref = safeMonitorReturnHref((await searchParams).return_to)
  return <MonitorDetails monitorId={monitorId} returnHref={returnHref} />
}
