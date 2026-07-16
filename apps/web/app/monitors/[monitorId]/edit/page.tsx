import { safeMonitorReturnHref } from "@/lib/monitor-navigation"
import { MonitorEdit } from "./monitor-edit"


export default async function EditMonitorPage({
  params,
  searchParams,
}: {
  params: Promise<{ monitorId: string }>
  searchParams: Promise<{ return_to?: string | string[] }>
}) {
  const { monitorId } = await params
  const returnHref = safeMonitorReturnHref((await searchParams).return_to)
  return <MonitorEdit monitorId={monitorId} returnHref={returnHref} />
}
