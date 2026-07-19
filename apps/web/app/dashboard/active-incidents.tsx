"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { AlertTriangleIcon } from "lucide-react"

import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { formatIncidentDuration, listAllActiveIncidents, type IncidentListDto } from "@/lib/incident-api"
import { formatMonitorTimestamp } from "@/lib/monitor-time"


type State =
  | { type: "loading" }
  | { type: "success"; data: IncidentListDto }
  | { type: "error" }

export function ActiveIncidents() {
  const [state, setState] = useState<State>({ type: "loading" })
  const [version, setVersion] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    void listAllActiveIncidents({ signal: controller.signal }).then((outcome) => {
      if (controller.signal.aborted || outcome.type === "cancelled") return
      setState(outcome.type === "success" ? { type: "success", data: outcome.data } : { type: "error" })
    })
    return () => controller.abort()
  }, [version])

  const total = state.type === "success" ? state.data.items.length : 0
  return (
    <Card>
      <CardHeader>
        <CardTitle>Active incidents</CardTitle>
        <CardDescription>{state.type === "loading" ? "Loading incidents…" : `${total} active incident${total === 1 ? "" : "s"} displayed.`}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {state.type === "loading" ? <LoadingState label="Loading active incidents" count={2} className="lg:grid-cols-1" /> : null}
        {state.type === "error" ? <ErrorState title="Unable to load active incidents" description="Current incident data could not be loaded. Retry the request." action={<Button variant="outline" type="button" onClick={() => setVersion((value) => value + 1)}>Try again</Button>} /> : null}
        {state.type === "success" && state.data.items.length === 0 ? <EmptyState title="No active incidents" description="All monitored services are currently clear of open incidents." /> : null}
        {state.type === "success" ? state.data.items.map((incident) => (
          <Link key={incident.id} href={`/monitors/incidents/${incident.id}`} className="rounded-lg border border-status-down/30 bg-status-down/10 p-3 transition-colors hover:bg-status-down/20">
            <div className="flex items-start gap-3">
              <AlertTriangleIcon className="mt-0.5 size-4 shrink-0 text-status-down-foreground" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="font-medium">{incident.monitor_name}</p>
                <p className="mt-1 text-sm capitalize text-muted-foreground">{incident.cause_category?.replaceAll("_", " ") ?? "Monitor incident"}</p>
                <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                  <div><dt className="text-muted-foreground">Opened</dt><dd><time dateTime={incident.opened_at} title={`UTC: ${incident.opened_at}`}>{formatMonitorTimestamp(incident.opened_at).display}</time></dd></div>
                  <div><dt className="text-muted-foreground">Current duration</dt><dd>{formatIncidentDuration(incident.duration_seconds)}</dd></div>
                </dl>
              </div>
            </div>
          </Link>
        )) : null}
      </CardContent>
    </Card>
  )
}
