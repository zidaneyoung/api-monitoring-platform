import { MonitorDetails } from "./monitor-details"
import { RecentChecks } from "./recent-checks"
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
  return (
    <>
      <MonitorDetails monitorId={monitorId} returnHref={returnHref} />
      <section aria-label="Monitor check history" className="mx-auto w-full max-w-6xl px-4 pb-8 sm:px-6 lg:px-8">
        <RecentChecks monitorId={monitorId} />
      </section>
    </>
  )
}
