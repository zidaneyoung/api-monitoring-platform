"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowLeftIcon, PencilIcon } from "lucide-react"
import { useEffect, useState } from "react"

import { StatusBadge } from "@/components/status-badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { getMonitor, type MonitorDto } from "@/lib/monitor-api"
import { MonitorDeleteButton } from "../monitor-delete-button"
import { MonitorStateButton, type MonitorMutationAction } from "../monitor-pause-button"


type DetailsState =
  | { type: "loading"; monitorId: string }
  | { type: "not_found"; monitorId: string }
  | { type: "error"; monitorId: string }
  | { type: "ready"; monitorId: string; monitor: MonitorDto }

const dateFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
})

function formatDate(value: string | null): string {
  return value ? dateFormatter.format(new Date(value)) : "—"
}

function formatDuration(seconds: number): string {
  if (seconds % 3600 === 0) return `${seconds / 3600} hour${seconds === 3600 ? "" : "s"}`
  if (seconds % 60 === 0) return `${seconds / 60} minute${seconds === 60 ? "" : "s"}`
  return `${seconds} seconds`
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <Card className="gap-1 py-4">
      <CardHeader className="px-4"><CardDescription>{label}</CardDescription><CardTitle className="text-xl">{value}</CardTitle></CardHeader>
    </Card>
  )
}

function LoadingDetails() {
  return (
    <main className="mx-auto flex w-full max-w-[94rem] flex-col gap-5 px-4 py-6 sm:px-6 lg:px-8" aria-busy="true">
      <span className="sr-only">Loading monitor details</span>
      <div className="h-8 w-40 animate-pulse rounded-md bg-muted" />
      <div className="h-14 w-96 max-w-full animate-pulse rounded-md bg-muted" />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">{Array.from({ length: 5 }, (_, index) => <div className="h-24 animate-pulse rounded-xl bg-muted" key={index} />)}</div>
    </main>
  )
}

function MessageDetails({
  title,
  description,
  retry,
}: {
  title: string
  description: string
  retry?: () => void
}) {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 py-8 sm:px-6 lg:px-8">
      <Card className="items-center py-12 text-center">
        <CardContent className="flex max-w-lg flex-col items-center gap-3">
          <h1>{title}</h1>
          <p className="text-muted-foreground">{description}</p>
          <div className="flex flex-wrap justify-center gap-2">
            {retry ? <Button variant="outline" type="button" onClick={retry}>Try again</Button> : null}
            <Link className={buttonVariants({ variant: "outline" })} href="/monitors"><ArrowLeftIcon data-icon="inline-start" />Back to monitors</Link>
          </div>
        </CardContent>
      </Card>
    </main>
  )
}

function DetailsContent({
  monitor,
  onMonitorChange,
  onDeleted,
}: {
  monitor: MonitorDto
  onMonitorChange: (monitor: MonitorDto) => void
  onDeleted: (monitorId: string) => void
}) {
  const [pendingMutation, setPendingMutation] = useState<MonitorMutationAction | null>(null)
  const configuration = [
    ["HTTP method", monitor.http_method],
    ["Interval", formatDuration(monitor.interval_seconds)],
    ["Timeout", formatDuration(monitor.timeout_seconds)],
    ["Accepted status", `${monitor.expected_status_min}–${monitor.expected_status_max}`],
    ["Failure threshold", String(monitor.failure_threshold)],
    ["Recovery threshold", String(monitor.recovery_threshold)],
  ]
  return (
    <main className="mx-auto flex w-full max-w-[94rem] flex-col gap-4 px-4 py-6 sm:px-6 lg:px-8 xl:px-11 xl:py-7">
      <Link className="inline-flex w-fit items-center gap-2 text-sm font-medium text-foreground transition-colors hover:text-link focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50" href="/monitors"><ArrowLeftIcon aria-hidden="true" />Back to monitors</Link>
      <header className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0"><div className="flex flex-wrap items-center gap-4"><h1 className="text-[2.25rem] font-semibold tracking-[-0.045em] sm:text-[2.45rem]">{monitor.name}</h1><StatusBadge status={monitor.status} className="px-3 py-1 text-base" /></div><a className="mt-1 block break-all text-base font-semibold text-link hover:underline" href={monitor.url}>{monitor.url}</a></div>
        <div className="flex flex-wrap items-center gap-3">
          <Link className={buttonVariants({ variant: "outline", size: "lg", className: "h-10 px-4" })} href={`/monitors/${monitor.id}/edit`}><PencilIcon data-icon="inline-start" />Edit</Link>
          <MonitorStateButton
            className="h-10 px-4"
            monitor={monitor}
            pendingAction={pendingMutation}
            onPendingActionChange={setPendingMutation}
            onChanged={onMonitorChange}
          />
          <MonitorDeleteButton
            className="h-10 px-4"
            monitor={monitor}
            pendingAction={pendingMutation}
            onPendingActionChange={setPendingMutation}
            onDeleted={onDeleted}
          />
        </div>
      </header>

      <dl className="mt-1 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <SummaryCard label="Current status" value={monitor.status[0].toUpperCase() + monitor.status.slice(1)} />
        <SummaryCard label="Latest response time" value={monitor.latest_response_time_ms === null ? "—" : `${monitor.latest_response_time_ms.toLocaleString()} ms`} />
        <SummaryCard label="Status code" value={monitor.latest_status_code === null ? "—" : String(monitor.latest_status_code)} />
        <SummaryCard label="Latest check" value={formatDate(monitor.last_checked_at)} />
        <SummaryCard label="Next check" value={formatDate(monitor.next_check_at)} />
      </dl>

      <div className="mt-1 grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(20rem,1fr)]">
        <Card><CardHeader><CardTitle>Response time</CardTitle><CardDescription>Response history will appear after check-history endpoints are implemented.</CardDescription></CardHeader><CardContent><p className="text-sm text-muted-foreground">No response history is included in this monitor-details response.</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Configuration</CardTitle><CardDescription>Monitor request and alert thresholds.</CardDescription></CardHeader><CardContent><dl>{configuration.map(([label, value]) => <div className="flex items-center justify-between gap-4 border-b py-2.5 last:border-b-0" key={label}><dt className="text-sm text-muted-foreground">{label}</dt><dd className="text-right text-sm font-semibold">{value}</dd></div>)}</dl></CardContent></Card>
        <Card><CardHeader><CardTitle>Recent checks</CardTitle><CardDescription>Check history is outside this workflow unit.</CardDescription></CardHeader><CardContent><p className="text-sm text-muted-foreground">No check history loaded.</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Incident history</CardTitle><CardDescription>Incident history is outside this workflow unit.</CardDescription></CardHeader><CardContent><p className="text-sm text-muted-foreground">No incident history loaded.</p></CardContent></Card>
      </div>
    </main>
  )
}

export function MonitorDetails({ monitorId }: { monitorId: string }) {
  const router = useRouter()
  const [requestVersion, setRequestVersion] = useState(0)
  const [state, setState] = useState<DetailsState>({ type: "loading", monitorId })

  useEffect(() => {
    let cancelled = false
    void getMonitor(monitorId).then((outcome) => {
      if (cancelled) return
      if (outcome.type === "success") setState({ type: "ready", monitorId, monitor: outcome.data })
      else if (outcome.type === "not_found") setState({ type: "not_found", monitorId })
      else setState({ type: "error", monitorId })
    })
    return () => { cancelled = true }
  }, [monitorId, requestVersion])

  if (state.type === "loading" || state.monitorId !== monitorId) return <LoadingDetails />
  if (state.type === "not_found") return <MessageDetails title="Monitor not found" description="This monitor does not exist or is not available to your account." />
  if (state.type === "error") return <MessageDetails title="Unable to display monitor" description="Monitor details could not be loaded. Try again." retry={() => { setState({ type: "loading", monitorId }); setRequestVersion((value) => value + 1) }} />
  return <DetailsContent monitor={state.monitor} onMonitorChange={(monitor) => setState({ type: "ready", monitorId, monitor })} onDeleted={() => { router.push("/monitors"); router.refresh() }} />
}
