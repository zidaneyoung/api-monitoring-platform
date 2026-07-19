"use client"

import {
  CircleCheckIcon,
  CircleHelpIcon,
  CirclePauseIcon,
  CircleXIcon,
} from "lucide-react"
import { useEffect, useState } from "react"

import { ErrorState, LoadingState } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { getMonitorSummary, type MonitorSummaryDto, type MonitorStatus } from "@/lib/monitor-api"

type SummaryState =
  | { type: "loading" }
  | { type: "ready"; data: MonitorSummaryDto }
  | { type: "error" }

const summaryMetrics = [
  { label: "Up", status: "up", icon: CircleCheckIcon },
  { label: "Down", status: "down", icon: CircleXIcon },
  { label: "Paused", status: "paused", icon: CirclePauseIcon },
  { label: "Unknown", status: "unknown", icon: CircleHelpIcon },
] satisfies Array<{ label: string; status: MonitorStatus; icon: typeof CircleCheckIcon }>

export function MonitorSummary() {
  const [state, setState] = useState<SummaryState>({ type: "loading" })
  const [version, setVersion] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    void getMonitorSummary({ signal: controller.signal }).then((outcome) => {
      if (controller.signal.aborted || outcome.type === "cancelled") return
      setState(outcome.type === "success"
        ? { type: "ready", data: outcome.data }
        : { type: "error" })
    })
    return () => controller.abort()
  }, [version])

  if (state.type === "loading") {
    return <LoadingState label="Loading monitor summary" count={5} className="sm:grid-cols-2 xl:grid-cols-5" />
  }
  if (state.type === "error") {
    return (
      <ErrorState
        title="Unable to load monitor summary"
        description="Monitor status counts could not be loaded. Retry the request."
        action={<Button variant="outline" type="button" onClick={() => { setState({ type: "loading" }); setVersion((value) => value + 1) }}>Try again</Button>}
      />
    )
  }

  return (
    <section aria-labelledby="monitor-summary" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <Card className="bg-primary text-primary-foreground ring-0">
        <CardHeader>
          <CardDescription className="text-primary-foreground/70">Monitors</CardDescription>
          <CardTitle id="monitor-summary" className="text-3xl font-semibold">{state.data.total}</CardTitle>
        </CardHeader>
      </Card>
      {summaryMetrics.map((metric) => {
        const Icon = metric.icon
        return (
          <Card key={metric.status} className="relative overflow-hidden">
            <CardHeader>
              <CardDescription>{metric.label}</CardDescription>
              <CardTitle className="text-3xl font-semibold">{state.data[metric.status]}</CardTitle>
            </CardHeader>
            <Icon className="absolute right-4 top-4 size-5 text-muted-foreground" aria-hidden="true" />
          </Card>
        )
      })}
    </section>
  )
}
