"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowLeftIcon, ClipboardIcon, ExternalLinkIcon, PencilIcon } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { StatusBadge } from "@/components/status-badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { getMonitor, type MonitorDto } from "@/lib/monitor-api"
import { monitorEditHref, monitorListHref } from "@/lib/monitor-navigation"
import { formatMonitorErrorCategory, formatMonitorResponseTime, formatMonitorStatusCode } from "@/lib/monitor-result"
import { formatMonitorTimestamp } from "@/lib/monitor-time"
import { MonitorDeleteButton } from "../monitor-delete-button"
import { MonitorStateButton, type MonitorMutationAction } from "../monitor-pause-button"


type DetailsState =
  | { type: "loading"; monitorId: string }
  | { type: "not_found"; monitorId: string }
  | { type: "error"; monitorId: string }
  | { type: "ready"; monitorId: string; monitor: MonitorDto }

function formatDuration(seconds: number): string {
  if (seconds % 3600 === 0) return `${seconds / 3600} hour${seconds === 3600 ? "" : "s"}`
  if (seconds % 60 === 0) return `${seconds / 60} minute${seconds === 60 ? "" : "s"}`
  return `${seconds} seconds`
}

function ConfigurationRows({ rows }: { rows: Array<[string, string]> }) {
  return (
    <dl>
      {rows.map(([label, value]) => (
        <div className="flex items-start justify-between gap-4 border-b py-3 first:pt-0 last:border-b-0 last:pb-0" key={label}>
          <dt className="text-sm text-muted-foreground">{label}</dt>
          <dd className="text-right text-sm font-semibold">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function EndpointUtilities({ url }: { url: string }) {
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null)

  async function copyEndpoint() {
    let timeout: ReturnType<typeof setTimeout> | undefined
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable")
      await Promise.race([
        navigator.clipboard.writeText(url),
        new Promise<never>((_, reject) => {
          timeout = setTimeout(() => reject(new Error("Clipboard timed out")), 2000)
        }),
      ])
      setFeedback({ type: "success", message: "Endpoint URL copied." })
    } catch {
      setFeedback({ type: "error", message: "Endpoint URL could not be copied. Select and copy it manually." })
    } finally {
      if (timeout) clearTimeout(timeout)
    }
  }

  return (
    <div className="grid gap-3">
      <a className="break-all text-sm font-semibold text-link hover:underline" href={url} target="_blank" rel="noopener noreferrer">
        {url}
      </a>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" type="button" onClick={copyEndpoint}>
          <ClipboardIcon data-icon="inline-start" />Copy endpoint
        </Button>
        <a className={buttonVariants({ variant: "outline", size: "sm" })} href={url} target="_blank" rel="noopener noreferrer">
          <ExternalLinkIcon data-icon="inline-start" />Open endpoint
        </a>
      </div>
      {feedback ? (
        <p className={feedback.type === "error" ? "text-sm text-destructive" : "text-sm text-muted-foreground"} role={feedback.type === "error" ? "alert" : "status"} aria-live="polite">
          {feedback.message}
        </p>
      ) : null}
    </div>
  )
}

function LoadingDetails() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 py-6 sm:px-6 lg:px-8" aria-busy="true">
      <span className="sr-only">Loading monitor details</span>
      <div className="h-8 w-40 animate-pulse rounded-md bg-muted" />
      <div className="h-14 w-96 max-w-full animate-pulse rounded-md bg-muted" />
      <div className="grid gap-4 md:grid-cols-2">{Array.from({ length: 4 }, (_, index) => <div className="h-44 animate-pulse rounded-xl bg-muted" key={index} />)}</div>
    </main>
  )
}

function MessageDetails({
  title,
  description,
  returnHref,
  retry,
}: {
  title: string
  description: string
  returnHref: string
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
            <Link className={buttonVariants({ variant: "outline" })} href={returnHref}><ArrowLeftIcon data-icon="inline-start" />Back to monitors</Link>
          </div>
        </CardContent>
      </Card>
    </main>
  )
}

function DetailsContent({
  monitor,
  returnHref,
  onMonitorChange,
  onDeleted,
}: {
  monitor: MonitorDto
  returnHref: string
  onMonitorChange: (monitor: MonitorDto) => void
  onDeleted: (monitorId: string) => void
}) {
  const [pendingMutation, setPendingMutation] = useState<MonitorMutationAction | null>(null)
  const stateDescription = monitor.status === "paused"
    ? "Checks are paused until this monitor is resumed."
    : monitor.status === "unknown"
      ? "No completed check has established this monitor’s health yet."
      : "This is the latest state stored for the monitor."

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 py-6 sm:px-6 lg:px-8 xl:py-8">
      <Link className={buttonVariants({ variant: "ghost", size: "sm", className: "w-fit px-2" })} href={returnHref}>
        <ArrowLeftIcon data-icon="inline-start" />Back to monitors
      </Link>

      <header>
        <h1 className="break-words text-[2.25rem] font-semibold tracking-[-0.045em] sm:text-[2.6rem]">{monitor.name}</h1>
        <p className="mt-1 text-muted-foreground">Monitor configuration and available management actions.</p>
      </header>

      <section aria-labelledby="monitor-current-state">
        <Card>
          <CardHeader>
            <CardTitle id="monitor-current-state">Current state</CardTitle>
            <CardDescription>{stateDescription}</CardDescription>
          </CardHeader>
          <CardContent><StatusBadge status={monitor.status} className="px-3 py-1 text-base" /></CardContent>
        </Card>
      </section>

      <div className="grid min-w-0 gap-4 md:grid-cols-2">
        <section aria-labelledby="monitor-endpoint-configuration">
          <Card className="h-full">
            <CardHeader><CardTitle id="monitor-endpoint-configuration">Endpoint configuration</CardTitle><CardDescription>The request destination and method.</CardDescription></CardHeader>
            <CardContent className="grid gap-5">
              <EndpointUtilities url={monitor.url} />
              <ConfigurationRows rows={[["HTTP method", monitor.http_method]]} />
            </CardContent>
          </Card>
        </section>

        <section aria-labelledby="monitor-schedule-configuration">
          <Card className="h-full">
            <CardHeader><CardTitle id="monitor-schedule-configuration">Schedule configuration</CardTitle><CardDescription>How often a future check may run and wait.</CardDescription></CardHeader>
            <CardContent><ConfigurationRows rows={[["Interval", formatDuration(monitor.interval_seconds)], ["Timeout", formatDuration(monitor.timeout_seconds)]]} /></CardContent>
          </Card>
        </section>

        <section aria-labelledby="monitor-success-criteria">
          <Card className="h-full">
            <CardHeader><CardTitle id="monitor-success-criteria">Success criteria</CardTitle><CardDescription>Accepted responses and consecutive-result thresholds.</CardDescription></CardHeader>
            <CardContent><ConfigurationRows rows={[["Accepted status", `${monitor.expected_status_min}–${monitor.expected_status_max}`], ["Failure threshold", String(monitor.failure_threshold)], ["Recovery threshold", String(monitor.recovery_threshold)]]} /></CardContent>
          </Card>
        </section>

        <section aria-labelledby="monitor-latest-check">
          <Card className="h-full">
            <CardHeader><CardTitle id="monitor-latest-check">Latest check</CardTitle><CardDescription>Most recent completed result stored by the monitoring worker.</CardDescription></CardHeader>
            <CardContent>
              <ConfigurationRows rows={[
                ["Completed", monitor.last_checked_at ? formatMonitorTimestamp(monitor.last_checked_at).display : "Not checked yet"],
                ["Response time", formatMonitorResponseTime(monitor.latest_response_time_ms)],
                ["HTTP status", formatMonitorStatusCode(monitor.latest_status_code)],
                ["Error", formatMonitorErrorCategory(monitor.latest_error_category) ?? "—"],
              ]} />
              {monitor.last_checked_at ? <time className="sr-only" dateTime={monitor.last_checked_at}>UTC: {monitor.last_checked_at}</time> : null}
            </CardContent>
          </Card>
        </section>

        <section aria-labelledby="monitor-available-actions">
          <Card className="h-full">
            <CardHeader><CardTitle id="monitor-available-actions">Available actions</CardTitle><CardDescription>Update this monitor or change whether future checks may run.</CardDescription></CardHeader>
            <CardContent className="grid gap-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                <Link className={buttonVariants({ variant: "outline", size: "lg", className: "justify-start" })} href={monitorEditHref(monitor.id, returnHref)}><PencilIcon data-icon="inline-start" />Edit monitor</Link>
                <MonitorStateButton
                  className="w-full justify-start sm:w-auto"
                  monitor={monitor}
                  pendingAction={pendingMutation}
                  onPendingActionChange={setPendingMutation}
                  onChanged={onMonitorChange}
                />
              </div>
              <div className="border-t border-destructive/20 pt-4">
                <MonitorDeleteButton
                  className="w-full justify-start sm:w-auto"
                  monitor={monitor}
                  pendingAction={pendingMutation}
                  onPendingActionChange={setPendingMutation}
                  onDeleted={onDeleted}
                />
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </main>
  )
}

export function MonitorDetails({
  monitorId,
  returnHref = monitorListHref(),
}: {
  monitorId: string
  returnHref?: string
}) {
  const router = useRouter()
  const [requestVersion, setRequestVersion] = useState(0)
  const [state, setState] = useState<DetailsState>({ type: "loading", monitorId })
  const latestReadRef = useRef(0)

  useEffect(() => {
    const controller = new AbortController()
    const readId = ++latestReadRef.current
    void getMonitor(monitorId, { signal: controller.signal }).then((outcome) => {
      if (readId !== latestReadRef.current || outcome.type === "cancelled") return
      if (outcome.type === "success") setState({ type: "ready", monitorId, monitor: outcome.data })
      else if (outcome.type === "not_found") setState({ type: "not_found", monitorId })
      else setState({ type: "error", monitorId })
    })
    return () => { controller.abort() }
  }, [monitorId, requestVersion])

  if (state.type === "loading" || state.monitorId !== monitorId) return <LoadingDetails />
  if (state.type === "not_found") return <MessageDetails title="Monitor not found" description="This monitor does not exist or is not available to your account." returnHref={returnHref} />
  if (state.type === "error") return <MessageDetails title="Unable to display monitor" description="Monitor details could not be loaded. Try again." returnHref={returnHref} retry={() => { setState({ type: "loading", monitorId }); setRequestVersion((value) => value + 1) }} />
  return <DetailsContent monitor={state.monitor} returnHref={returnHref} onMonitorChange={(monitor) => setState({ type: "ready", monitorId, monitor })} onDeleted={() => { router.push(returnHref); router.refresh() }} />
}
