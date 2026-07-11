import Link from "next/link"
import {
  ArrowLeftIcon,
  Clock3Icon,
  MapPinIcon,
  ShieldAlertIcon,
  ShieldCheckIcon,
} from "lucide-react"
import type { ReactNode } from "react"

import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { StatusBadge } from "@/components/status-badge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"

import { getMonitorById } from "../../monitor-data"
import { getIncidentById, type IncidentCheck, type IncidentRecord, type IncidentTimelineEvent } from "../../incidents-data"

type PageProps = {
  params: Promise<{
    incidentId: string
  }>
  searchParams: Promise<{
    state?: string | string[]
  }>
}

const timeFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
})

function formatTime(value: string) {
  return timeFormatter.format(new Date(value))
}

function normalizeState(value: string | string[] | undefined) {
  const state = Array.isArray(value) ? value[0] : value

  if (state === "loading" || state === "error") {
    return state
  }

  return "ready"
}

function compareByTimeThenId(
  a: { id: string; occurredAt?: string; checkedAt?: string },
  b: { id: string; occurredAt?: string; checkedAt?: string }
) {
  const aTime = new Date(a.occurredAt ?? a.checkedAt ?? "").getTime()
  const bTime = new Date(b.occurredAt ?? b.checkedAt ?? "").getTime()

  if (aTime !== bTime) {
    return aTime - bTime
  }

  return a.id.localeCompare(b.id)
}

function IncidentStatusBadge({ incident }: { incident: IncidentRecord }) {
  const isOpen = incident.section === "open"

  return (
    <Badge
      variant={isOpen ? "destructive" : "secondary"}
      className={cn(
        isOpen
          ? "bg-status-down text-status-down-foreground"
          : "bg-status-up text-status-up-foreground"
      )}
    >
      {isOpen ? <ShieldAlertIcon data-icon="inline-start" aria-hidden="true" /> : <ShieldCheckIcon data-icon="inline-start" aria-hidden="true" />}
      {incident.status}
    </Badge>
  )
}

function CheckStatusBadge({ status }: { status: IncidentCheck["status"] }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        status === "failed" && "border-status-down/40 bg-status-down/10 text-status-down-foreground",
        status === "degraded" && "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
        status === "recovered" && "border-status-up/40 bg-status-up/10 text-status-up-foreground"
      )}
    >
      {status}
    </Badge>
  )
}

function DetailItem({ label, value, icon }: { label: string; value: ReactNode; icon?: ReactNode }) {
  return (
    <div>
      <dt className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        {icon}
        {label}
      </dt>
      <dd className="mt-1 text-sm font-medium">{value}</dd>
    </div>
  )
}

export default async function IncidentDetailsPage({ params, searchParams }: PageProps) {
  const [{ incidentId }, requestedSearchParams] = await Promise.all([params, searchParams])
  const requestedState = normalizeState(requestedSearchParams.state)

  if (requestedState === "loading") {
    return <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8"><LoadingState label="Loading incident details" count={3} /></main>
  }

  if (requestedState === "error") {
    return (
      <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 lg:px-8"><ErrorState title="Unable to load incident" description="Incident details could not be loaded. Retry the request." action={<Button variant="outline" nativeButton={false} render={<Link href={`/monitors/incidents/${incidentId}`} />}>Try again</Button>} /></main>
    )
  }

  const incident = getIncidentById(incidentId)

  if (!incident) {
    return (
      <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 lg:px-8"><EmptyState title="Incident not found" description="No incident matches this link. It may have been removed or the address may be incorrect." action={<Button variant="outline" nativeButton={false} render={<Link href="/monitors/incidents" />}><ArrowLeftIcon data-icon="inline-start" />Back to incident history</Button>} /></main>
    )
  }

  const monitor = getMonitorById(incident.monitorId)
  const isOpen = incident.section === "open"
  const relatedChecks = [...incident.relatedChecks].sort(compareByTimeThenId)
  const timeline = [...incident.timeline].sort(compareByTimeThenId)

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
      <div>
        <Button variant="outline" size="sm" nativeButton={false} render={<Link href="/monitors/incidents" />}>
          <ArrowLeftIcon data-icon="inline-start" />
          Back to incident history
        </Button>
      </div>

      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{incident.monitorName}</p>
          <h1 className="mt-1">{incident.title}</h1>
          <p className="mt-2 max-w-3xl text-muted-foreground">{incident.summary}</p>
        </div>
        <IncidentStatusBadge incident={incident} />
      </header>

      <Card className={cn(isOpen ? "border-l-4 border-l-status-down" : "border-l-4 border-l-status-up")}>
        <CardHeader>
          <CardTitle>Incident overview</CardTitle>
          <CardDescription>Current state, associated monitor, and incident timing.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <DetailItem label="State" value={incident.status} />
            <DetailItem label="Opened" value={formatTime(incident.openedAt)} />
            <DetailItem label={incident.resolvedAt ? "Resolved" : "Resolution"} value={incident.resolvedAt ? formatTime(incident.resolvedAt) : "Still open"} />
            <DetailItem label={isOpen ? "Current duration" : "Final duration"} value={incident.duration} icon={<Clock3Icon className="size-3.5" aria-hidden="true" />} />
          </dl>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Associated monitor</CardTitle>
            <CardDescription>{monitor ? monitor.url : "Monitor details unavailable in mock data."}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                {monitor ? (
                  <Link className="text-lg font-semibold hover:underline" href={`/monitors/${monitor.id}`}>
                    {monitor.name}
                  </Link>
                ) : (
                  <div className="text-lg font-semibold">{incident.monitorName}</div>
                )}
                <div className="mt-1 text-sm text-muted-foreground">Incident source: {incident.monitorName}</div>
              </div>
              {monitor ? <StatusBadge status={monitor.status} /> : null}
            </div>
            {monitor ? (
              <dl className="mt-6 grid gap-4 sm:grid-cols-2">
                <DetailItem label="Latest check" value={monitor.lastCheck} />
                <DetailItem label="Response time" value={monitor.responseTime} />
              </dl>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Triggering failure</CardTitle>
            <CardDescription>Failure fields render as text from mock data.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <dl className="grid gap-4 sm:grid-cols-2">
              <DetailItem label="Check ID" value={incident.triggeringFailure.checkId} />
              <DetailItem label="Observed" value={formatTime(incident.triggeringFailure.observedAt)} />
              <DetailItem label="Location" value={incident.triggeringFailure.location} icon={<MapPinIcon className="size-3.5" aria-hidden="true" />} />
              <DetailItem label="Status code" value={incident.triggeringFailure.statusCode ?? "No HTTP status"} />
              <DetailItem label="Response time" value={incident.triggeringFailure.responseTime} />
            </dl>
            <div>
              <div className="text-xs font-medium text-muted-foreground">Failure</div>
              <p className="mt-1 text-sm">{incident.triggeringFailure.message}</p>
            </div>
            <div>
              <div className="text-xs font-medium text-muted-foreground">Body preview</div>
              <pre className="mt-1 overflow-x-auto rounded-lg bg-muted p-3 text-xs whitespace-pre-wrap text-muted-foreground">
                <code>{incident.triggeringFailure.bodyPreview}</code>
              </pre>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Related checks</CardTitle>
          <CardDescription>Checks associated with this incident.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Check</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Time</TableHead>
                <TableHead>Location</TableHead>
                <TableHead>Status code</TableHead>
                <TableHead>Response</TableHead>
                <TableHead>Failure</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {relatedChecks.map((check) => (
                <TableRow key={check.id}>
                  <TableCell className="font-mono text-xs">{check.id}</TableCell>
                  <TableCell><CheckStatusBadge status={check.status} /></TableCell>
                  <TableCell>{formatTime(check.checkedAt)}</TableCell>
                  <TableCell>{check.location}</TableCell>
                  <TableCell>{check.statusCode ?? "None"}</TableCell>
                  <TableCell>{check.responseTime}</TableCell>
                  <TableCell className="max-w-sm whitespace-normal text-muted-foreground">{check.failure}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Incident timeline</CardTitle>
          <CardDescription>Events are sorted chronologically with a stable ID fallback.</CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="grid gap-4">
            {timeline.map((event: IncidentTimelineEvent) => (
              <li key={event.id} className="grid gap-3 border-l-2 border-border pl-4">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <h2 className="text-sm font-medium">{event.title}</h2>
                  <time className="text-sm text-muted-foreground" dateTime={event.occurredAt}>
                    {formatTime(event.occurredAt)}
                  </time>
                </div>
                <p className="text-sm text-muted-foreground">{event.description}</p>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </main>
  )
}
