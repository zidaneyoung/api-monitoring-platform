"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { useEffect, useState } from "react"
import {
  ArrowLeftIcon,
  CalendarDaysIcon,
  CheckCircle2Icon,
  Clock3Icon,
  ShieldAlertIcon,
  ShieldCheckIcon,
} from "lucide-react"

import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  formatIncidentDuration,
  getIncident,
  incidentSection,
  type IncidentCheckDto,
  type IncidentDto,
  type IncidentOutcome,
} from "@/lib/incident-api"
import { cn } from "@/lib/utils"

type DetailState =
  | { type: "loading" }
  | { type: "success"; incident: IncidentDto }
  | { type: "not_found" }
  | { type: "error" }

const timeFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
})

function formatTime(value: string | null) {
  if (!value) return "Not recorded"
  const parsed = new Date(value)
  return Number.isFinite(parsed.getTime()) ? timeFormatter.format(parsed) : "Unavailable"
}

function toDetailState(outcome: IncidentOutcome<IncidentDto>): DetailState {
  if (outcome.type === "success") return { type: "success", incident: outcome.data }
  if (outcome.type === "not_found") return { type: "not_found" }
  return { type: "error" }
}

function IncidentStatusBadge({ incident }: { incident: IncidentDto }) {
  const open = incidentSection(incident.status) === "open"
  return (
    <Badge variant={open ? "destructive" : "secondary"} className={cn(open ? "bg-status-down text-status-down-foreground" : "bg-status-up text-status-up-foreground")}>
      {open ? <ShieldAlertIcon data-icon="inline-start" aria-hidden="true" /> : <ShieldCheckIcon data-icon="inline-start" aria-hidden="true" />}
      {incident.status}
    </Badge>
  )
}

function CheckCard({ title, check }: { title: string; check: IncidentCheckDto | null }) {
  if (!check) return null
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">{title}</CardTitle><CardDescription>{check.success ? "Successful monitor check" : "Failed monitor check"}</CardDescription></CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-3"><div><p className="text-xs text-muted-foreground">Completed</p><p className="mt-1 text-sm font-medium">{formatTime(check.completed_at)}</p></div><div><p className="text-xs text-muted-foreground">HTTP status</p><p className="mt-1 text-sm font-medium">{check.http_status_code ?? "Not recorded"}</p></div><div><p className="text-xs text-muted-foreground">Response time</p><p className="mt-1 text-sm font-medium">{check.response_time_ms === null ? "Not recorded" : `${check.response_time_ms} ms`}</p></div>{check.error_message ? <div className="sm:col-span-3"><p className="text-xs text-muted-foreground">Diagnostic</p><p className="mt-1 text-sm leading-6">{check.error_message}</p></div> : null}</CardContent>
    </Card>
  )
}

export default function IncidentDetailsPage() {
  const { incidentId } = useParams<{ incidentId?: string }>()
  const [state, setState] = useState<DetailState>({ type: "loading" })
  const [requestVersion, setRequestVersion] = useState(0)

  useEffect(() => {
    if (!incidentId) {
      return
    }
    const controller = new AbortController()
    void getIncident(incidentId, { signal: controller.signal }).then((outcome) => {
      if (!controller.signal.aborted) setState(toDetailState(outcome))
    })
    return () => controller.abort()
  }, [incidentId, requestVersion])

  if (!incidentId) {
    return <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 lg:px-8"><EmptyState title="Incident not found" description="No incident matches this link, or it belongs to another account." action={<Button variant="outline" nativeButton={false} render={<Link href="/monitors/incidents" />}><ArrowLeftIcon data-icon="inline-start" />Back to incident history</Button>} /></main>
  }
  if (state.type === "loading") {
    return <main className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 lg:px-8"><LoadingState label="Loading incident" count={3} /></main>
  }
  if (state.type === "not_found") {
    return <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 lg:px-8"><EmptyState title="Incident not found" description="No incident matches this link, or it belongs to another account." action={<Button variant="outline" nativeButton={false} render={<Link href="/monitors/incidents" />}><ArrowLeftIcon data-icon="inline-start" />Back to incident history</Button>} /></main>
  }
  if (state.type === "error") {
    return <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 lg:px-8"><ErrorState title="Unable to load incident" description="Incident details could not be loaded. Retry the request." action={<Button variant="outline" type="button" onClick={() => setRequestVersion((value) => value + 1)}>Try again</Button>} /></main>
  }

  const { incident } = state
  const open = incidentSection(incident.status) === "open"
  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="flex flex-col gap-6">
        <Button className="w-fit" variant="ghost" nativeButton={false} render={<Link href="/monitors/incidents" />}><ArrowLeftIcon data-icon="inline-start" />Incident history</Button>
        <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start"><div><p className="text-sm text-muted-foreground">{incident.monitor.name}</p><h1 className="mt-1 capitalize">{incident.cause_category?.replaceAll("_", " ") ?? "Monitor incident"}</h1><p className="mt-2 max-w-2xl text-sm text-muted-foreground">{incident.cause_message ?? "Monitor state changed after consecutive checks."}</p></div><IncidentStatusBadge incident={incident} /></header>
        <Card><CardHeader><CardTitle>Incident overview</CardTitle><CardDescription>All timestamps are shown in UTC.</CardDescription></CardHeader><CardContent className="grid gap-5 sm:grid-cols-3"><div><p className="flex items-center gap-2 text-xs text-muted-foreground"><CalendarDaysIcon className="size-3.5" />Opened</p><p className="mt-1 text-sm font-medium">{formatTime(incident.opened_at)}</p></div><div><p className="flex items-center gap-2 text-xs text-muted-foreground"><CalendarDaysIcon className="size-3.5" />{incident.resolved_at ? "Resolved" : "Resolution"}</p><p className="mt-1 text-sm font-medium">{formatTime(incident.resolved_at)}</p></div><div><p className="flex items-center gap-2 text-xs text-muted-foreground"><Clock3Icon className="size-3.5" />Duration</p><p className="mt-1 text-sm font-medium">{formatIncidentDuration(incident.duration_seconds)}</p></div></CardContent></Card>
        <div className="grid gap-4 lg:grid-cols-2"><CheckCard title="Triggering failure" check={incident.triggering_check} /><CheckCard title="Recovery check" check={incident.recovery_check} /></div>
        <Card><CardHeader><CardTitle>Incident timeline</CardTitle><CardDescription>Lifecycle events recorded for this incident.</CardDescription></CardHeader><CardContent>{incident.events.length === 0 ? <p className="text-sm text-muted-foreground">No timeline events were recorded.</p> : <Table><TableHeader><TableRow><TableHead>When</TableHead><TableHead>Event</TableHead><TableHead>Details</TableHead></TableRow></TableHeader><TableBody>{incident.events.map((event) => <TableRow key={event.id}><TableCell className="whitespace-nowrap text-sm">{formatTime(event.occurred_at)}</TableCell><TableCell className="capitalize"><span className="inline-flex items-center gap-2"><CheckCircle2Icon className={cn("size-4", event.event_type === "resolved" && !open ? "text-status-up" : "text-status-down")} />{event.event_type.replaceAll("_", " ")}</span></TableCell><TableCell className="text-muted-foreground">{event.message ?? "No additional details."}</TableCell></TableRow>)}</TableBody></Table>}</CardContent></Card>
      </div>
    </main>
  )
}
