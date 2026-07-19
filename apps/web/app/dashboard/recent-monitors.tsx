"use client"

import Link from "next/link"
import { useEffect, useState } from "react"

import { ErrorState, LoadingState } from "@/components/states"
import { StatusBadge } from "@/components/status-badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { listMonitors, type MonitorDto } from "@/lib/monitor-api"

type RecentMonitorState =
  | { type: "loading" }
  | { type: "ready"; monitors: MonitorDto[] }
  | { type: "error" }

export function RecentMonitors() {
  const [state, setState] = useState<RecentMonitorState>({ type: "loading" })
  const [version, setVersion] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    void listMonitors(1, 5, { signal: controller.signal }).then((outcome) => {
      if (controller.signal.aborted || outcome.type === "cancelled") return
      setState(outcome.type === "success"
        ? { type: "ready", monitors: outcome.data.items }
        : { type: "error" })
    })
    return () => controller.abort()
  }, [version])

  if (state.type === "loading") {
    return <LoadingState label="Loading recent monitors" count={1} className="lg:grid-cols-1" />
  }
  if (state.type === "error") {
    return (
      <ErrorState
        title="Unable to load recent monitors"
        description="Current monitor states could not be loaded. Retry the request."
        action={<Button variant="outline" type="button" onClick={() => { setState({ type: "loading" }); setVersion((value) => value + 1) }}>Try again</Button>}
      />
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent monitors</CardTitle>
        <CardDescription>Current persisted state across monitored endpoints.</CardDescription>
      </CardHeader>
      <CardContent className="divide-y">
        {state.monitors.length === 0 ? <p className="text-sm text-muted-foreground">No monitors yet.</p> : null}
        {state.monitors.map((monitor) => (
          <div key={monitor.id} className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <Link href={`/monitors/${monitor.id}`} className="font-medium hover:underline">{monitor.name}</Link>
              <p className="mt-0.5 truncate text-sm text-muted-foreground">{monitor.url}</p>
            </div>
            <StatusBadge status={monitor.status} />
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
