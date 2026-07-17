"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { AlertTriangleIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { formatIncidentDuration, listIncidents, type IncidentListDto } from "@/lib/incident-api"


type State =
  | { type: "loading" }
  | { type: "success"; data: IncidentListDto }
  | { type: "error" }

export function ActiveIncidents() {
  const [state, setState] = useState<State>({ type: "loading" })
  const [version, setVersion] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    void listIncidents("open", 1, 5, { signal: controller.signal }).then((outcome) => {
      if (controller.signal.aborted) return
      setState(outcome.type === "success" ? { type: "success", data: outcome.data } : { type: "error" })
    })
    return () => controller.abort()
  }, [version])

  const total = state.type === "success" ? state.data.total : 0
  return (
    <Card>
      <CardHeader>
        <CardTitle>Active incidents</CardTitle>
        <CardDescription>{state.type === "loading" ? "Loading incidents…" : `${total} issue${total === 1 ? "" : "s"} need attention.`}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {state.type === "error" ? <Button variant="outline" type="button" onClick={() => setVersion((value) => value + 1)}>Retry incident history</Button> : null}
        {state.type === "success" && state.data.total === 0 ? <p className="text-sm text-muted-foreground">No active incidents.</p> : null}
        {state.type === "success" ? state.data.items.map((incident) => (
          <Link key={incident.id} href={`/monitors/incidents/${incident.id}`} className="rounded-lg border border-status-down/30 bg-status-down/10 p-3 transition-colors hover:bg-status-down/20">
            <div className="flex items-start gap-3"><AlertTriangleIcon className="mt-0.5 size-4 shrink-0 text-status-down-foreground" aria-hidden="true" /><div className="min-w-0"><p className="font-medium capitalize">{incident.cause_category?.replaceAll("_", " ") ?? "Monitor incident"}</p><p className="mt-1 text-sm text-muted-foreground">{incident.monitor_name} · {formatIncidentDuration(incident.duration_seconds)}</p></div></div>
          </Link>
        )) : null}
      </CardContent>
    </Card>
  )
}
