"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
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

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

import type { IncidentRecord, IncidentSection } from "../incidents-data"

type StatusFilter = "all" | IncidentSection

const pageSizes = [10, 25, 50]

const timeFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
})

function formatTime(value: string) {
  return timeFormatter.format(new Date(value))
}

function IncidentStatusBadge({ incident }: { incident: IncidentRecord }) {
  const tone = incident.section

  return (
    <Badge
      variant="outline"
      className={cn(
        "incident-status-badge border-transparent",
        tone === "open"
          ? "bg-status-down text-status-down-foreground"
          : "bg-status-up text-status-up-foreground"
      )}
      data-tone={tone}
    >
      <CircleDotIcon data-icon="inline-start" aria-hidden="true" />
      {incident.status}
    </Badge>
  )
}

function IncidentMeta({
  label,
  value,
  icon,
  divided,
}: {
  label: string
  value: string
  icon: React.ReactNode
  divided?: boolean
}) {
  return (
    <div className={cn("incident-meta min-w-0 py-2 sm:py-0", divided && "incident-meta-divided sm:pl-5")}>
      <dt className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
        {icon}
        {label}
      </dt>
      <dd className="mt-1 pl-5 text-[0.82rem] font-medium leading-snug text-foreground sm:whitespace-nowrap">{value}</dd>
    </div>
  )
}

function IncidentCard({ incident }: { incident: IncidentRecord }) {
  return (
    <Card className="incident-record gap-0 py-0 shadow-none" data-tone={incident.section}>
      <CardHeader className="gap-0 px-4 pt-4 pb-0">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-xs text-muted-foreground">{incident.monitorName}</p>
            <CardTitle className="mt-1 text-[0.95rem] font-semibold tracking-[-0.01em]">
              <Link
                href={`/monitors/incidents/${incident.id}`}
                className="rounded-sm outline-none hover:underline hover:underline-offset-4 focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                {incident.title}
              </Link>
            </CardTitle>
          </div>
          <IncidentStatusBadge incident={incident} />
        </div>
      </CardHeader>
      <CardContent className="px-4 pt-3 pb-4">
        <dl className="grid sm:grid-cols-3">
          <IncidentMeta
            label="Opened"
            value={formatTime(incident.openedAt)}
            icon={<CalendarDaysIcon className="size-3.5" strokeWidth={1.8} aria-hidden="true" />}
          />
          <IncidentMeta
            label={incident.resolvedAt ? "Resolved" : "Resolution"}
            value={incident.resolvedAt ? formatTime(incident.resolvedAt) : "Still open"}
            icon={<CalendarDaysIcon className="size-3.5" strokeWidth={1.8} aria-hidden="true" />}
            divided
          />
          <IncidentMeta
            label="Duration"
            value={incident.duration}
            icon={<Clock3Icon className="size-3.5" strokeWidth={1.8} aria-hidden="true" />}
            divided
          />
        </dl>
        <p className="mt-3 text-xs leading-relaxed text-muted-foreground">{incident.summary}</p>
      </CardContent>
    </Card>
  )
}

function EmptySection({ tone }: { tone: IncidentSection }) {
  return (
    <div className="incident-empty rounded-lg border border-dashed px-4 py-10 text-center text-sm text-muted-foreground">
      No {tone} incidents match these filters.
    </div>
  )
}

function PaginationControls({
  count,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
}: {
  count: number
  page: number
  pageSize: number
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
}) {
  const totalPages = Math.max(1, Math.ceil(count / pageSize))
  const start = count === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, count)

  return (
    <>
      <p className="text-xs text-muted-foreground">
        Showing {start} to {end} of {count} incidents
      </p>
      <div className="flex items-center gap-2">
        <Button
          className="incident-page-button"
          variant="outline"
          size="icon"
          type="button"
          disabled={page === 1}
          onClick={() => onPageChange(page - 1)}
          aria-label="Previous page"
        >
          <ChevronLeftIcon aria-hidden="true" />
        </Button>
        <Button className="incident-page-number" variant="outline" size="icon" type="button" aria-current="page">
          {page}
        </Button>
        <Button
          className="incident-page-button"
          variant="outline"
          size="icon"
          type="button"
          disabled={page === totalPages}
          onClick={() => onPageChange(page + 1)}
          aria-label="Next page"
        >
          <ChevronRightIcon aria-hidden="true" />
        </Button>
        <label className="relative ml-2">
          <span className="sr-only">Incidents per page</span>
          <select
            className="incident-control h-9 appearance-none rounded-lg border px-3 pr-9 text-xs font-medium outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            value={pageSize}
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
          >
            {pageSizes.map((size) => (
              <option key={size} value={size}>{size} / page</option>
            ))}
          </select>
          <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-3 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        </label>
      </div>
    </>
  )
}

function IncidentPanel({
  title,
  description,
  incidents,
  tone,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
}: {
  title: string
  description: string
  incidents: IncidentRecord[]
  tone: IncidentSection
  page: number
  pageSize: number
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
}) {
  const startIndex = (page - 1) * pageSize
  const visibleIncidents = incidents.slice(startIndex, startIndex + pageSize)
  const Icon = tone === "open" ? CircleAlertIcon : CheckIcon

  return (
    <Card className="incident-panel gap-0 py-0 shadow-none">
      <CardHeader className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-0 px-4 py-4">
        <span
          className={cn(
            "incident-section-icon row-span-2 grid size-9 place-items-center rounded-full",
            tone === "open"
              ? "bg-status-down text-status-down-foreground"
              : "bg-status-up text-status-up-foreground"
          )}
          data-tone={tone}
        >
          <Icon className="size-5" strokeWidth={2} aria-hidden="true" />
        </span>
        <CardTitle className="text-base font-semibold tracking-[-0.015em]">{title}</CardTitle>
        <Badge
          variant="outline"
          className={cn(
            "incident-count-badge row-span-2 border-transparent",
            tone === "open"
              ? "bg-status-down text-status-down-foreground"
              : "bg-status-up text-status-up-foreground"
          )}
          data-tone={tone}
        >
          {incidents.length} incidents
        </Badge>
        <p className="col-start-2 text-xs leading-relaxed text-muted-foreground">{description}</p>
      </CardHeader>
      <CardContent className="grid gap-2 px-4 pb-4">
        {visibleIncidents.length > 0
          ? visibleIncidents.map((incident) => <IncidentCard key={incident.id} incident={incident} />)
          : <EmptySection tone={tone} />}
      </CardContent>
      <CardFooter className="incident-panel-footer flex flex-wrap justify-between gap-3 border-t px-4 py-3">
        <PaginationControls
          count={incidents.length}
          page={page}
          pageSize={pageSize}
          onPageChange={onPageChange}
          onPageSizeChange={onPageSizeChange}
        />
      </CardFooter>
    </Card>
  )
}

export function IncidentHistoryClient({
  openIncidents,
  resolvedIncidents,
}: {
  openIncidents: IncidentRecord[]
  resolvedIncidents: IncidentRecord[]
}) {
  const [query, setQuery] = useState("")
  const [status, setStatus] = useState<StatusFilter>("all")
  const [openPage, setOpenPage] = useState(1)
  const [resolvedPage, setResolvedPage] = useState(1)
  const [openPageSize, setOpenPageSize] = useState(10)
  const [resolvedPageSize, setResolvedPageSize] = useState(10)

  const filteredIncidents = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase()

    return [...openIncidents, ...resolvedIncidents].filter((incident) => {
      const matchesStatus = status === "all" || incident.section === status
      const matchesQuery = normalizedQuery.length === 0 || [
        incident.monitorName,
        incident.title,
        incident.status,
        incident.summary,
      ].some((value) => value.toLocaleLowerCase().includes(normalizedQuery))

      return matchesStatus && matchesQuery
    })
  }, [openIncidents, query, resolvedIncidents, status])

  const filteredOpen = filteredIncidents.filter((incident) => incident.section === "open")
  const filteredResolved = filteredIncidents.filter((incident) => incident.section === "resolved")

  function resetPages() {
    setOpenPage(1)
    setResolvedPage(1)
  }

  return (
    <main className="incident-history-page min-h-[calc(100svh-3.5rem)] px-4 py-7 sm:px-6 lg:px-8 xl:px-14 xl:py-8">
      <div className="mx-auto flex w-full max-w-[86rem] flex-col gap-4">
        <header className="grid gap-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
          <div>
            <h1>Incident history</h1>
            <p className="mt-1 text-sm text-muted-foreground">Review open and resolved monitor incidents.</p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:min-w-72">
            <Card className="incident-summary-card gap-0 py-0 shadow-none">
              <CardContent className="px-4 py-3">
                <p className="text-xs text-muted-foreground">Open</p>
                <p className="mt-1 text-2xl font-semibold leading-none tracking-[-0.025em]">{openIncidents.length}</p>
              </CardContent>
            </Card>
            <Card className="incident-summary-card gap-0 py-0 shadow-none">
              <CardContent className="px-4 py-3">
                <p className="text-xs text-muted-foreground">Resolved</p>
                <p className="mt-1 text-2xl font-semibold leading-none tracking-[-0.025em]">{resolvedIncidents.length}</p>
              </CardContent>
            </Card>
          </div>
        </header>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <label className="relative block w-full sm:max-w-[30rem]">
            <span className="sr-only">Search incidents</span>
            <SearchIcon className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted-foreground" strokeWidth={1.8} aria-hidden="true" />
            <Input
              className="incident-control h-12 pl-11 text-sm"
              type="search"
              placeholder="Search incidents..."
              value={query}
              onChange={(event) => {
                setQuery(event.target.value)
                resetPages()
              }}
            />
          </label>
          <label className="relative w-full sm:w-44">
            <span className="sr-only">Filter by incident status</span>
            <select
              className="incident-control h-12 w-full appearance-none rounded-lg border px-4 pr-10 text-sm font-medium outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as StatusFilter)
                resetPages()
              }}
            >
              <option value="all">All status</option>
              <option value="open">Open</option>
              <option value="resolved">Resolved</option>
            </select>
            <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-4 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          </label>
        </div>

        <div className="grid items-start gap-4 xl:grid-cols-2">
          <IncidentPanel
            title="Open incidents"
            description="Active issues still impacting monitored endpoints."
            incidents={filteredOpen}
            tone="open"
            page={openPage}
            pageSize={openPageSize}
            onPageChange={setOpenPage}
            onPageSizeChange={(pageSize) => {
              setOpenPageSize(pageSize)
              setOpenPage(1)
            }}
          />
          <IncidentPanel
            title="Resolved incidents"
            description="Closed issues with recorded resolution times."
            incidents={filteredResolved}
            tone="resolved"
            page={resolvedPage}
            pageSize={resolvedPageSize}
            onPageChange={setResolvedPage}
            onPageSizeChange={(pageSize) => {
              setResolvedPageSize(pageSize)
              setResolvedPage(1)
            }}
          />
        </div>
      </div>
    </main>
  )
}
