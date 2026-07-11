import Link from "next/link"
import { AlertTriangleIcon, ArrowLeftIcon, InboxIcon } from "lucide-react"

import { buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

import { mockIncidents } from "../incidents-data"
import { getMonitorById, mockMonitors } from "../monitor-data"
import { MonitorDetails, type MonitorIncidentSummary } from "./monitor-details"

type PageProps = {
  params: Promise<{ monitorId: string }>
  searchParams: Promise<{ state?: string | string[] }>
}

const timeFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
})

function normalizeState(value: string | string[] | undefined) {
  const state = Array.isArray(value) ? value[0] : value
  return state === "loading" || state === "empty" || state === "error" ? state : "ready"
}

function LoadingState() {
  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8" aria-busy="true">
      <div className="h-7 w-36 rounded-md bg-muted" />
      <div className="h-12 w-72 max-w-full rounded-md bg-muted" />
      <Card><CardHeader><div className="h-5 w-36 rounded-md bg-muted" /><div className="h-4 w-56 rounded-md bg-muted" /></CardHeader><CardContent><div className="h-24 rounded-lg bg-muted" /></CardContent></Card>
      <div className="grid gap-6 lg:grid-cols-2"><Card><CardContent><div className="h-64 rounded-lg bg-muted" /></CardContent></Card><Card><CardContent><div className="h-64 rounded-lg bg-muted" /></CardContent></Card></div>
    </main>
  )
}

function MessageState({
  title,
  description,
  error = false,
}: {
  title: string
  description: string
  error?: boolean
}) {
  const Icon = error ? AlertTriangleIcon : InboxIcon

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
      <Card className={error ? "border-destructive/40 py-12 text-center" : "items-center py-12 text-center"}>
        <CardContent className="flex flex-col items-center gap-3">
          <Icon className={error ? "size-10 text-destructive" : "size-10 text-muted-foreground"} aria-hidden="true" />
          <div><h1>{title}</h1><p className="mt-1 text-muted-foreground">{description}</p></div>
          <Link className={buttonVariants({ variant: "outline" })} href="/monitors"><ArrowLeftIcon data-icon="inline-start" />Back to monitors</Link>
        </CardContent>
      </Card>
    </main>
  )
}

export function generateStaticParams() {
  return mockMonitors.map((monitor) => ({ monitorId: monitor.id }))
}

export default async function MonitorDetailsPage({ params, searchParams }: PageProps) {
  const [{ monitorId }, resolvedSearchParams] = await Promise.all([params, searchParams])
  const state = normalizeState(resolvedSearchParams.state)

  if (state === "loading") return <LoadingState />
  if (state === "error") return <MessageState error title="Unable to display monitor" description="Something went wrong while preparing this mock monitor detail view. Try again." />

  const monitor = getMonitorById(monitorId)
  if (!monitor) return <MessageState error title="Monitor not found" description="The requested mock monitor does not exist in this dataset." />
  if (state === "empty") return <MessageState title="No checks yet" description="This monitor will show check results after its first scheduled run." />

  const incidents: MonitorIncidentSummary[] = mockIncidents
    .filter((incident) => incident.monitorId === monitor.id)
    .map((incident) => ({
      id: incident.id,
      title: incident.title,
      status: incident.status,
      openedAt: timeFormatter.format(new Date(incident.openedAt)),
      duration: incident.duration,
      resolved: incident.section === "resolved",
    }))

  return <MonitorDetails monitor={monitor} incidents={incidents} />
}
