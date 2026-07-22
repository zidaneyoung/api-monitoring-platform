"use client"

import { useEffect, useState } from "react"
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { getMonitorResponseTimes, type MonitorResponseTimeSeriesDto } from "@/lib/monitor-api"
import { formatMonitorTimestamp, parseApiTimestamp } from "@/lib/monitor-time"

type ResponseTimeChartState =
  | { type: "loading" }
  | { type: "ready"; data: MonitorResponseTimeSeriesDto }
  | { type: "error" }

function chartTime(value: string): string {
  const timestamp = parseApiTimestamp(value)
  return timestamp === null
    ? "Unavailable"
    : new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(timestamp)
}

function tooltipTime(value: string): string {
  return formatMonitorTimestamp(value).display
}

export function ResponseTimeChart({ monitorId }: { monitorId: string }) {
  const [version, setVersion] = useState(0)
  const [state, setState] = useState<ResponseTimeChartState>({ type: "loading" })

  useEffect(() => {
    const controller = new AbortController()
    void getMonitorResponseTimes(monitorId, { signal: controller.signal }).then((outcome) => {
      if (controller.signal.aborted || outcome.type === "cancelled") return
      setState(outcome.type === "success"
        ? { type: "ready", data: outcome.data }
        : { type: "error" })
    })
    return () => controller.abort()
  }, [monitorId, version])

  if (state.type === "loading") {
    return <LoadingState label="Loading response-time chart" count={1} className="lg:grid-cols-1" />
  }
  if (state.type === "error") {
    return (
      <ErrorState
        title="Unable to load response times"
        description="Persisted response-time history could not be loaded. Retry the request."
        action={<Button type="button" variant="outline" onClick={() => { setState({ type: "loading" }); setVersion((value) => value + 1) }}>Try again</Button>}
      />
    )
  }

  const chartData = state.data.points
    .map((point) => ({ ...point, timestamp: parseApiTimestamp(point.completed_at) }))
    .filter((point): point is typeof point & { timestamp: number } => point.timestamp !== null)
    .sort((left, right) => left.timestamp - right.timestamp)
  const measuredPoints = chartData.filter((point) => point.response_time_ms !== null)
  if (chartData.length === 0 || measuredPoints.length === 0) {
    return (
      <EmptyState
        title="No response-time data"
        description="No response-time measurements were recorded in the last 24 hours."
      />
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Response time</CardTitle>
        <CardDescription>Last 24 hours · Persisted completed checks</CardDescription>
      </CardHeader>
      <CardContent>
        <div
          role="img"
          aria-label={`Response time in milliseconds over the last 24 hours. ${measuredPoints.length} measured checks. Missing response times appear as gaps.`}
          className="h-64 w-full min-w-0 sm:h-72"
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} accessibilityLayer margin={{ top: 8, right: 12, bottom: 8, left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="completed_at"
                tickFormatter={chartTime}
                minTickGap={24}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                width={64}
                unit=" ms"
                allowDecimals={false}
                domain={[0, "auto"]}
                tickLine={false}
                axisLine={false}
                label={{ value: "Milliseconds", angle: -90, position: "insideLeft" }}
              />
              <Tooltip
                labelFormatter={(value) => tooltipTime(String(value))}
                formatter={(value) => [`${String(value)} ms`, "Response time"]}
              />
              <Line
                type="linear"
                dataKey="response_time_ms"
                name="Response time"
                stroke="var(--color-chart-line)"
                strokeWidth={2}
                connectNulls={false}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
