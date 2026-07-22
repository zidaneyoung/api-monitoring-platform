"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import {
  CalendarDaysIcon,
  CheckIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CircleAlertIcon,
  CircleDotIcon,
  Clock3Icon,
  SearchIcon,
} from "lucide-react"

import { ErrorState, LoadingState } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  formatIncidentDuration,
  incidentSection,
  listIncidents,
  type IncidentListDto,
  type IncidentListItemDto,
  type IncidentOutcome,
  type IncidentSection,
} from "@/lib/incident-api"
import { formatMonitorTimestamp } from "@/lib/monitor-time"
import { cn } from "@/lib/utils"

type StatusFilter = "all" | IncidentSection
type LoadState =
  | { type: "loading" }
  | { type: "success"; data: IncidentListDto }
  | { type: "error"; outcome: Exclude<IncidentOutcome<never>, { type: "success" }> }

const pageSizes = [10, 25, 50]
function formatTime(value: string) {
  return formatMonitorTimestamp(value).display
}

function loadState(outcome: IncidentOutcome<IncidentListDto>): LoadState {
  return outcome.type === "success"
    ? { type: "success", data: outcome.data }
    : { type: "error", outcome }
}

function IncidentStatusBadge({ incident }: { incident: IncidentListItemDto }) {
  const section = incidentSection(incident.status)
  return (
    <Badge
      variant="outline"
      className={cn(
        "incident-status-badge border-transparent",
        section === "open"
          ? "bg-status-down text-status-down-foreground"
          : "bg-status-up text-status-up-foreground",
      )}
      data-tone={section}
    >
      <CircleDotIcon data-icon="inline-start" aria-hidden="true" />
      {incident.status}
    </Badge>
  )
}

function IncidentMeta({ label, value, icon, divided }: {
  label: string
  value: string
  icon: React.ReactNode
  divided?: boolean
}) {
  return (
    <div className={cn("incident-meta min-w-0 py-2 sm:py-0", divided && "incident-meta-divided sm:pl-5")}>
      <dt className="flex items-center gap-2 text-xs font-medium text-muted-foreground">{icon}{label}</dt>
      <dd className="mt-1 pl-5 text-[0.82rem] font-medium leading-snug text-foreground sm:whitespace-nowrap">{value}</dd>
    </div>
  )
}

function IncidentCard({ incident }: { incident: IncidentListItemDto }) {
  const section = incidentSection(incident.status)
  const title = incident.cause_category ? incident.cause_category.replaceAll("_", " ") : "Monitor incident"
  return (
    <Card className="incident-record gap-0 py-0 shadow-none" data-tone={section}>
      <CardHeader className="gap-0 px-4 pt-4 pb-0">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-xs text-muted-foreground">{incident.monitor_name}</p>
            <CardTitle className="mt-1 text-[0.95rem] font-semibold tracking-[-0.01em]">
              <Link href={`/monitors/incidents/${incident.id}`} className="rounded-sm capitalize outline-none hover:underline hover:underline-offset-4 focus-visible:ring-3 focus-visible:ring-ring/50">
                {title}
              </Link>
            </CardTitle>
          </div>
          <IncidentStatusBadge incident={incident} />
        </div>
      </CardHeader>
      <CardContent className="px-4 pt-3 pb-4">
        <dl className="grid sm:grid-cols-3">
          <IncidentMeta label="Opened" value={formatTime(incident.opened_at)} icon={<CalendarDaysIcon className="size-3.5" strokeWidth={1.8} aria-hidden="true" />} />
          <IncidentMeta label={incident.resolved_at ? "Resolved" : "Resolution"} value={incident.resolved_at ? formatTime(incident.resolved_at) : "Still open"} icon={<CalendarDaysIcon className="size-3.5" strokeWidth={1.8} aria-hidden="true" />} divided />
          <IncidentMeta label={section === "resolved" ? "Final duration" : "Current duration"} value={formatIncidentDuration(incident.duration_seconds)} icon={<Clock3Icon className="size-3.5" strokeWidth={1.8} aria-hidden="true" />} divided />
        </dl>
        <p className="mt-3 text-xs leading-relaxed text-muted-foreground">{incident.cause_message ?? "Monitor state changed after consecutive checks."}</p>
      </CardContent>
    </Card>
  )
}

function PaginationControls({ data, onPageChange, onPageSizeChange }: {
  data: IncidentListDto
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
}) {
  const start = data.total === 0 ? 0 : (data.page - 1) * data.page_size + 1
  const end = Math.min(data.page * data.page_size, data.total)
  return (
    <>
      <p className="text-xs text-muted-foreground">Showing {start} to {end} of {data.total} incidents</p>
      <div className="flex items-center gap-2">
        <Button className="incident-page-button" variant="outline" size="icon" type="button" disabled={data.page === 1} onClick={() => onPageChange(data.page - 1)} aria-label="Previous page"><ChevronLeftIcon aria-hidden="true" /></Button>
        <Button className="incident-page-number" variant="outline" size="icon" type="button" aria-current="page">{data.page}</Button>
        <Button className="incident-page-button" variant="outline" size="icon" type="button" disabled={data.page === data.pages} onClick={() => onPageChange(data.page + 1)} aria-label="Next page"><ChevronRightIcon aria-hidden="true" /></Button>
        <label className="relative ml-2"><span className="sr-only">Incidents per page</span><select className="incident-control h-9 appearance-none rounded-lg border px-3 pr-9 text-xs font-medium outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50" value={data.page_size} onChange={(event) => onPageSizeChange(Number(event.target.value))}>{pageSizes.map((size) => <option key={size} value={size}>{size} / page</option>)}</select><ChevronDownIcon className="pointer-events-none absolute top-1/2 right-3 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden="true" /></label>
      </div>
    </>
  )
}

function IncidentPanel({ title, description, section, state, query, onPageChange, onPageSizeChange, retry }: {
  title: string
  description: string
  section: IncidentSection
  state: LoadState
  query: string
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
  retry: () => void
}) {
  const Icon = section === "open" ? CircleAlertIcon : CheckIcon
  const visibleIncidents = state.type === "success"
    ? state.data.items.filter((incident) => [incident.monitor_name, incident.status, incident.cause_category ?? "", incident.cause_message ?? ""].some((value) => value.toLocaleLowerCase().includes(query)))
    : []
  return (
    <Card className="incident-panel gap-0 py-0 shadow-none">
      <CardHeader className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-0 px-4 py-4">
        <span className={cn("incident-section-icon row-span-2 grid size-9 place-items-center rounded-full", section === "open" ? "bg-status-down text-status-down-foreground" : "bg-status-up text-status-up-foreground")} data-tone={section}><Icon className="size-5" strokeWidth={2} aria-hidden="true" /></span>
        <CardTitle className="text-base font-semibold tracking-[-0.015em]">{title}</CardTitle>
        <Badge variant="outline" className={cn("incident-count-badge row-span-2 border-transparent", section === "open" ? "bg-status-down text-status-down-foreground" : "bg-status-up text-status-up-foreground")} data-tone={section}>{state.type === "success" ? state.data.total : "…"} incidents</Badge>
        <p className="col-start-2 text-xs leading-relaxed text-muted-foreground">{description}</p>
      </CardHeader>
      <CardContent className="grid gap-2 px-4 pb-4">
        {state.type === "loading" ? <LoadingState label={`Loading ${section} incidents`} count={2} /> : null}
        {state.type === "error" ? <ErrorState title="Unable to load incidents" description="Incident history could not be loaded. Retry the request." action={<Button variant="outline" type="button" onClick={retry}>Try again</Button>} /> : null}
        {state.type === "success" && visibleIncidents.length === 0 ? <div className="incident-empty rounded-lg border border-dashed px-4 py-10 text-center text-sm text-muted-foreground">No {section} incidents match these filters.</div> : null}
        {state.type === "success" ? visibleIncidents.map((incident) => <IncidentCard key={incident.id} incident={incident} />) : null}
      </CardContent>
      {state.type === "success" ? <CardFooter className="incident-panel-footer flex flex-wrap justify-between gap-3 border-t px-4 py-3"><PaginationControls data={state.data} onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} /></CardFooter> : null}
    </Card>
  )
}

export function IncidentHistoryClient() {
  const [openPage, setOpenPage] = useState(1)
  const [resolvedPage, setResolvedPage] = useState(1)
  const [openPageSize, setOpenPageSize] = useState(10)
  const [resolvedPageSize, setResolvedPageSize] = useState(10)
  const [openState, setOpenState] = useState<LoadState>({ type: "loading" })
  const [resolvedState, setResolvedState] = useState<LoadState>({ type: "loading" })
  const [query, setQuery] = useState("")
  const [status, setStatus] = useState<StatusFilter>("all")
  const [requestVersion, setRequestVersion] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    void Promise.all([
      listIncidents("open", openPage, openPageSize, { signal: controller.signal }),
      listIncidents("resolved", resolvedPage, resolvedPageSize, { signal: controller.signal }),
    ]).then(([open, resolved]) => {
      if (controller.signal.aborted) return
      setOpenState(loadState(open))
      setResolvedState(loadState(resolved))
    })
    return () => controller.abort()
  }, [openPage, openPageSize, requestVersion, resolvedPage, resolvedPageSize])

  const normalizedQuery = useMemo(() => query.trim().toLocaleLowerCase(), [query])
  const retry = () => setRequestVersion((value) => value + 1)
  const showOpen = status === "all" || status === "open"
  const showResolved = status === "all" || status === "resolved"
  const openTotal = openState.type === "success" ? openState.data.total : 0
  const resolvedTotal = resolvedState.type === "success" ? resolvedState.data.total : 0

  return (
    <main className="incident-history-page min-h-[calc(100svh-3.5rem)] px-4 py-7 sm:px-6 lg:px-8 xl:px-14 xl:py-8">
      <div className="mx-auto flex w-full max-w-[86rem] flex-col gap-4">
        <header className="grid gap-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start"><div><h1>Incident history</h1><p className="mt-1 text-sm text-muted-foreground">Review open and resolved monitor incidents.</p></div><div className="grid grid-cols-2 gap-3 sm:min-w-72"><Card className="incident-summary-card gap-0 py-0 shadow-none"><CardContent className="px-4 py-3"><p className="text-xs text-muted-foreground">Open</p><p className="mt-1 text-2xl font-semibold leading-none tracking-[-0.025em]">{openTotal}</p></CardContent></Card><Card className="incident-summary-card gap-0 py-0 shadow-none"><CardContent className="px-4 py-3"><p className="text-xs text-muted-foreground">Resolved</p><p className="mt-1 text-2xl font-semibold leading-none tracking-[-0.025em]">{resolvedTotal}</p></CardContent></Card></div></header>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><label className="relative block w-full sm:max-w-[30rem]"><span className="sr-only">Search incidents</span><SearchIcon className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted-foreground" strokeWidth={1.8} aria-hidden="true" /><Input className="incident-control h-12 pl-11 text-sm" type="search" placeholder="Search incidents..." value={query} onChange={(event) => setQuery(event.target.value)} /></label><label className="relative w-full sm:w-44"><span className="sr-only">Filter by incident status</span><select className="incident-control h-12 w-full appearance-none rounded-lg border px-4 pr-10 text-sm font-medium outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50" value={status} onChange={(event) => setStatus(event.target.value as StatusFilter)}><option value="all">All status</option><option value="open">Open</option><option value="resolved">Resolved</option></select><ChevronDownIcon className="pointer-events-none absolute top-1/2 right-4 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" /></label></div>
        <div className="grid items-start gap-4 xl:grid-cols-2">
          {showOpen ? <IncidentPanel title="Open incidents" description="Active issues still impacting monitored endpoints." section="open" state={openState} query={normalizedQuery} onPageChange={setOpenPage} onPageSizeChange={(pageSize) => { setOpenPageSize(pageSize); setOpenPage(1) }} retry={retry} /> : null}
          {showResolved ? <IncidentPanel title="Resolved incidents" description="Closed issues with recorded resolution times." section="resolved" state={resolvedState} query={normalizedQuery} onPageChange={setResolvedPage} onPageSizeChange={(pageSize) => { setResolvedPageSize(pageSize); setResolvedPage(1) }} retry={retry} /> : null}
        </div>
      </div>
    </main>
  )
}
