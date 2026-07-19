"use client"

import { useEffect, useState } from "react"

import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { listRecentChecks, type MonitorCheckListDto } from "@/lib/monitor-api"
import { formatMonitorErrorCategory, formatMonitorResponseTime, formatMonitorStatusCode } from "@/lib/monitor-result"
import { formatMonitorTimestamp } from "@/lib/monitor-time"

type RecentChecksState =
  | { type: "loading" }
  | { type: "ready"; data: MonitorCheckListDto }
  | { type: "error" }

const PAGE_SIZE = 5

export function RecentChecks({ monitorId }: { monitorId: string }) {
  const [page, setPage] = useState(1)
  const [version, setVersion] = useState(0)
  const [state, setState] = useState<RecentChecksState>({ type: "loading" })

  useEffect(() => {
    const controller = new AbortController()
    void listRecentChecks(monitorId, page, PAGE_SIZE, { signal: controller.signal }).then((outcome) => {
      if (controller.signal.aborted || outcome.type === "cancelled") return
      setState(outcome.type === "success"
        ? { type: "ready", data: outcome.data }
        : { type: "error" })
    })
    return () => controller.abort()
  }, [monitorId, page, version])

  if (state.type === "loading") {
    return <LoadingState label="Loading recent checks" count={1} className="lg:grid-cols-1" />
  }
  if (state.type === "error") {
    return (
      <ErrorState
        title="Unable to load recent checks"
        description="Recent monitor results could not be loaded. Retry the request."
        action={<Button type="button" variant="outline" onClick={() => { setState({ type: "loading" }); setVersion((value) => value + 1) }}>Try again</Button>}
      />
    )
  }
  if (state.data.total === 0) {
    return <EmptyState title="No completed checks" description="This monitor has not completed a check yet." />
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent checks</CardTitle>
        <CardDescription>Newest completed results from persisted monitor history.</CardDescription>
      </CardHeader>
      <CardContent className="divide-y">
        {state.data.items.map((check) => {
          const timestamp = formatMonitorTimestamp(check.completed_at)
          return (
            <article key={check.id} className="grid gap-3 py-4 first:pt-0 last:pb-0 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
              <div>
                <Badge variant="outline" className={check.success ? "border-status-up-foreground/35 bg-status-up text-status-up-foreground" : "border-status-down-foreground/35 bg-status-down text-status-down-foreground"}>
                  {check.success ? "Success" : "Failure"}
                </Badge>
                <div className="mt-2 text-sm text-muted-foreground">
                  <time dateTime={check.completed_at} title={`UTC: ${check.completed_at}`}>{timestamp.display}</time>
                </div>
              </div>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:text-right">
                <div><dt className="text-muted-foreground">Response</dt><dd className="font-medium">{formatMonitorResponseTime(check.response_time_ms)}</dd></div>
                <div><dt className="text-muted-foreground">HTTP status</dt><dd className="font-medium">{formatMonitorStatusCode(check.http_status_code)}</dd></div>
                {!check.success ? <div className="col-span-2"><dt className="text-muted-foreground">Error</dt><dd className="font-medium text-destructive">{formatMonitorErrorCategory(check.error_category) ?? "Monitoring error"}</dd></div> : null}
              </dl>
            </article>
          )
        })}
      </CardContent>
      <CardFooter className="flex items-center justify-between border-t px-6 py-4">
        <p className="text-sm text-muted-foreground">Page {state.data.page} of {state.data.pages}</p>
        <div className="flex gap-2">
          <Button type="button" variant="outline" disabled={state.data.page === 1} onClick={() => { setState({ type: "loading" }); setPage((value) => Math.max(1, value - 1)) }}>Previous</Button>
          <Button type="button" variant="outline" disabled={state.data.page === state.data.pages} onClick={() => { setState({ type: "loading" }); setPage((value) => Math.min(state.data.pages, value + 1)) }}>Next</Button>
        </div>
      </CardFooter>
    </Card>
  )
}
