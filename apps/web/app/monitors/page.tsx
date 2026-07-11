import Link from "next/link"
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  Clock3Icon,
  ShieldAlertIcon,
  ShieldCheckIcon,
} from "lucide-react"
import type { ReactNode } from "react"

import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

import { getIncidents } from "./incidents-data"
import type { IncidentRecord } from "./incidents-data"

type PageProps = {
  searchParams: Promise<{ state?: string }>
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

  if (state === "loading" || state === "empty" || state === "error") {
    return state
  }

  return "ready"
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

function IncidentMeta({ label, value, icon }: { label: string; value: string; icon?: ReactNode }) {
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

function IncidentCard({ incident }: { incident: IncidentRecord }) {
  const isOpen = incident.section === "open"

  return (
    <Card className={cn(isOpen ? "border-l-4 border-l-status-down bg-status-down/10" : "border-l-4 border-l-status-up bg-status-up/10")}>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <CardDescription>{incident.monitorName}</CardDescription>
            <CardTitle className="mt-1">
              <Link href={`/monitors/incidents/${incident.id}`} className="hover:underline">
                {incident.title}
              </Link>
            </CardTitle>
          </div>
          <IncidentStatusBadge incident={incident} />
        </div>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <IncidentMeta label="Opened" value={formatTime(incident.openedAt)} />
          <IncidentMeta label={incident.resolvedAt ? "Resolved" : "Resolution"} value={incident.resolvedAt ? formatTime(incident.resolvedAt) : "Still open"} />
          <IncidentMeta label="Duration" value={incident.duration} icon={<Clock3Icon className="size-3.5" aria-hidden="true" />} />
        </dl>
        <p className="mt-4 text-sm text-muted-foreground">{incident.summary}</p>
      </CardContent>
    </Card>
  )
}

function PaginationPlaceholder() {
  return (
    <CardFooter className="justify-between gap-3">
      <Button variant="outline" size="sm" type="button" disabled>
        <ChevronLeftIcon data-icon="inline-start" />
        Previous
      </Button>
      <span className="text-sm text-muted-foreground">Page 1 of 3</span>
      <Button variant="outline" size="sm" type="button" disabled>
        Next
        <ChevronRightIcon data-icon="inline-end" />
      </Button>
    </CardFooter>
  )
}

function IncidentSection({
  title,
  description,
  incidents,
  tone,
}: {
  title: string
  description: string
  incidents: IncidentRecord[]
  tone: "open" | "resolved"
}) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2>{title}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
        <Badge
          variant="outline"
          className={tone === "open" ? "border-status-down/40 text-status-down-foreground" : "border-status-up/40 text-status-up-foreground"}
        >
          {incidents.length} incidents
        </Badge>
      </div>
      <div className="grid gap-4">
        {incidents.map((incident) => (
          <IncidentCard key={incident.id} incident={incident} />
        ))}
      </div>
      <Card>
        <PaginationPlaceholder />
      </Card>
    </section>
  )
}

export default async function MonitorsPage({ searchParams }: PageProps) {
  const requestedState = normalizeState((await searchParams).state)
  const openIncidents = getIncidents("open")
  const resolvedIncidents = getIncidents("resolved")

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1>Incident history</h1>
          <p className="mt-1 text-muted-foreground">Review open and resolved monitor incidents.</p>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:min-w-64">
          <Card size="sm">
            <CardContent>
              <div className="text-sm text-muted-foreground">Open</div>
              <div className="mt-1 text-2xl font-semibold">{openIncidents.length}</div>
            </CardContent>
          </Card>
          <Card size="sm">
            <CardContent>
              <div className="text-sm text-muted-foreground">Resolved</div>
              <div className="mt-1 text-2xl font-semibold">{resolvedIncidents.length}</div>
            </CardContent>
          </Card>
        </div>
      </header>

      {requestedState === "loading" ? <LoadingState label="Loading incident history" /> : null}
      {requestedState === "empty" ? <EmptyState title="No incidents yet" description="No outages have been detected. Open and resolved incidents will appear here when a monitor reports one." /> : null}
      {requestedState === "error" ? <ErrorState title="Unable to load incident history" description="Incident history could not be loaded. Retry the request." action={<Button variant="outline" nativeButton={false} render={<Link href="/monitors" />}>Try again</Button>} /> : null}
      {requestedState === "ready" ? (
        <div className="grid gap-8 xl:grid-cols-2">
          <IncidentSection
            title="Open incidents"
            description="Active issues still impacting monitored endpoints."
            incidents={openIncidents}
            tone="open"
          />
          <IncidentSection
            title="Resolved incidents"
            description="Closed issues with recorded resolution times."
            incidents={resolvedIncidents}
            tone="resolved"
          />
        </div>
      ) : null}
    </main>
  )
}
