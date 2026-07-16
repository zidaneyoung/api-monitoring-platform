"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  MoreVerticalIcon,
  PencilIcon,
  PlusIcon,
} from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { StatusBadge } from "@/components/status-badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"
import { listMonitors, type MonitorDto, type MonitorListDto } from "@/lib/monitor-api"
import { monitorDetailsHref, monitorEditHref, monitorListHref } from "@/lib/monitor-navigation"
import { MonitorDeleteButton } from "./monitor-delete-button"
import { MonitorStateButton, type MonitorMutationAction } from "./monitor-pause-button"


type ListState =
  | { type: "loading" }
  | { type: "error" }
  | { type: "ready"; data: MonitorListDto }

const dateFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
})

function latestCheck(monitor: MonitorDto): { label: string; time: string } {
  if (monitor.status === "paused") {
    return {
      label: "Paused",
      time: monitor.last_checked_at ? dateFormatter.format(new Date(monitor.last_checked_at)) : "No completed check",
    }
  }
  if (!monitor.last_checked_at) return { label: "Not checked yet", time: "Awaiting first run" }
  return { label: "Last checked", time: dateFormatter.format(new Date(monitor.last_checked_at)) }
}

function responseTime(monitor: MonitorDto): string {
  return monitor.latest_response_time_ms === null
    ? "—"
    : `${monitor.latest_response_time_ms.toLocaleString()} ms`
}

function statusCode(monitor: MonitorDto): string {
  return monitor.latest_status_code === null ? "—" : String(monitor.latest_status_code)
}

function MonitorActions({
  monitor,
  returnHref,
  onNavigate,
  onMonitorChange,
  onMonitorDelete,
}: {
  monitor: MonitorDto
  returnHref: string
  onNavigate: () => void
  onMonitorChange: (monitor: MonitorDto) => void
  onMonitorDelete: (monitorId: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [pendingMutation, setPendingMutation] = useState<MonitorMutationAction | null>(null)

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => {
      if (pendingMutation === null) setOpen(nextOpen)
    }}>
      <DialogTrigger
        render={
          <Button
            variant="outline"
            size="icon-lg"
            type="button"
            aria-label={`Actions for ${monitor.name}`}
            title={`Actions for ${monitor.name}`}
          />
        }
      >
        <MoreVerticalIcon />
      </DialogTrigger>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>{monitor.name}</DialogTitle>
          <DialogDescription>Edit configuration or pause future checks.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          <Link
            className={cn(buttonVariants({ variant: "outline", size: "lg" }), "justify-start")}
            href={monitorEditHref(monitor.id, returnHref)}
            onClick={onNavigate}
          >
            <PencilIcon data-icon="inline-start" />Edit monitor
          </Link>
          <MonitorStateButton
            className="justify-start"
            monitor={monitor}
            pendingAction={pendingMutation}
            onPendingActionChange={setPendingMutation}
            onChanged={(updated) => { onMonitorChange(updated); setOpen(false) }}
          />
          <div className="mt-1 border-t border-destructive/20 pt-3">
            <MonitorDeleteButton
              className="w-full justify-start"
              monitor={monitor}
              pendingAction={pendingMutation}
              onPendingActionChange={setPendingMutation}
              onDeleted={(monitorId) => { onMonitorDelete(monitorId); setOpen(false) }}
            />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export function MonitorList({
  initialPage = 1,
  initialPageSize = 10,
}: {
  initialPage?: number
  initialPageSize?: number
}) {
  const router = useRouter()
  const [pagination, setPagination] = useState({
    page: initialPage,
    pageSize: initialPageSize,
    sourcePage: initialPage,
    sourcePageSize: initialPageSize,
  })
  const [requestVersion, setRequestVersion] = useState(0)
  const [state, setState] = useState<ListState>({ type: "loading" })
  const restoredPositionKey = useRef<string | null>(null)
  const { page, pageSize } = pagination

  if (pagination.sourcePage !== initialPage || pagination.sourcePageSize !== initialPageSize) {
    setState({ type: "loading" })
    setPagination({
      page: initialPage,
      pageSize: initialPageSize,
      sourcePage: initialPage,
      sourcePageSize: initialPageSize,
    })
  }

  useEffect(() => {
    let cancelled = false
    void listMonitors(page, pageSize).then((outcome) => {
      if (cancelled) return
      if (outcome.type === "success") {
        if (page > outcome.data.pages) {
          setState({ type: "loading" })
          setPagination((current) => ({ ...current, page: outcome.data.pages }))
          router.replace(monitorListHref(outcome.data.pages, pageSize), { scroll: false })
          return
        }
        setState({ type: "ready", data: outcome.data })
        return
      }
      setState({ type: "error" })
    })
    return () => { cancelled = true }
  }, [page, pageSize, requestVersion, router])

  const data = state.type === "ready" ? state.data : null
  const firstVisible = data && data.total > 0 ? (data.page - 1) * data.page_size + 1 : 0
  const lastVisible = data ? Math.min(data.page * data.page_size, data.total) : 0
  const returnHref = monitorListHref(page, pageSize)

  useEffect(() => {
    if (!data || restoredPositionKey.current === returnHref) return
    restoredPositionKey.current = returnHref
    try {
      const storageKey = `monitor-list-scroll:${returnHref}`
      const storedPosition = window.sessionStorage.getItem(storageKey)
      if (storedPosition === null) return
      window.sessionStorage.removeItem(storageKey)
      window.requestAnimationFrame(() => window.scrollTo({ top: Number(storedPosition), behavior: "instant" }))
    } catch {
      // Scroll restoration is a progressive enhancement.
    }
  }, [data, returnHref])

  const rememberListPosition = () => {
    try {
      window.sessionStorage.setItem(`monitor-list-scroll:${returnHref}`, String(window.scrollY))
    } catch {
      // Navigation remains functional when session storage is unavailable.
    }
  }

  const navigateToPage = (nextPage: number, nextPageSize = pageSize) => {
    setState({ type: "loading" })
    setPagination((current) => ({ ...current, page: nextPage, pageSize: nextPageSize }))
    router.push(monitorListHref(nextPage, nextPageSize), { scroll: false })
  }
  const replaceMonitor = (updated: MonitorDto) => setState((current) => current.type === "ready"
    ? { type: "ready", data: { ...current.data, items: current.data.items.map((monitor) => monitor.id === updated.id ? updated : monitor) } }
    : current)
  const removeMonitor = (monitorId: string) => {
    if (data?.items.length === 1 && data.page > 1) {
      setState({ type: "loading" })
      setPagination((current) => ({ ...current, page: data.page - 1 }))
      router.replace(monitorListHref(data.page - 1, pageSize), { scroll: false })
      return
    }
    setState((current) => {
      if (current.type !== "ready") return current
      const total = Math.max(0, current.data.total - 1)
      return {
        type: "ready",
        data: {
          ...current.data,
          items: current.data.items.filter((monitor) => monitor.id !== monitorId),
          total,
          pages: Math.max(1, Math.ceil(total / current.data.page_size)),
        },
      }
    })
  }

  return (
    <main className="relative mx-auto flex w-full max-w-[94rem] flex-col gap-5 overflow-hidden px-4 py-9 sm:px-6 lg:px-10 xl:px-12 xl:py-12">
      <header className="relative z-10 flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-[2.6rem] font-semibold tracking-[-0.045em] xl:text-[3rem]">Monitors</h1>
          <p className="mt-1.5 max-w-2xl text-base text-muted-foreground xl:text-lg">Track availability and response times for your endpoints.</p>
        </div>
        <Link className={cn(buttonVariants({ size: "lg" }), "h-14 rounded-xl px-6 text-base shadow-sm")} href="/monitors/new">
          <PlusIcon data-icon="inline-start" />
          Create monitor
        </Link>
      </header>

      {state.type === "loading" ? <LoadingState label="Loading monitors" count={3} className="xl:grid-cols-3" /> : null}
      {state.type === "error" ? (
        <ErrorState
          title="Unable to load monitors"
          description="Monitor data could not be loaded. Retry the request."
          action={<Button variant="outline" type="button" onClick={() => { setState({ type: "loading" }); setRequestVersion((value) => value + 1) }}>Try again</Button>}
        />
      ) : null}
      {data && data.total === 0 ? (
        <EmptyState
          title="No monitors yet"
          description="No endpoints are being checked. Create your first monitor to start tracking availability."
          action={<Link className={buttonVariants()} href="/monitors/new"><PlusIcon data-icon="inline-start" />Create monitor</Link>}
        />
      ) : null}

      {data && data.total > 0 ? (
        <Card className="relative z-10 gap-0 overflow-hidden py-0">
          <CardHeader className="px-6 py-6 sm:px-8 sm:pt-7 sm:pb-4">
            <CardTitle className="text-xl">All monitors</CardTitle>
            <CardDescription className="text-base">Authenticated monitors owned by your account.</CardDescription>
          </CardHeader>
          <CardContent className="px-0 sm:px-8">
            <div className="hidden overflow-x-auto md:block">
              <Table className="min-w-[860px]">
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="h-12 px-2 text-sm font-medium text-foreground">Monitor</TableHead>
                    <TableHead className="h-12 px-2 text-sm font-medium text-foreground">Status</TableHead>
                    <TableHead className="h-12 px-2 text-sm font-medium text-foreground">Latest check</TableHead>
                    <TableHead className="h-12 px-2 text-sm font-medium text-foreground">Response time</TableHead>
                    <TableHead className="h-12 px-2 text-sm font-medium text-foreground">Status code</TableHead>
                    <TableHead className="h-12 px-2 text-right text-sm font-medium text-foreground">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.items.map((monitor) => {
                    const check = latestCheck(monitor)
                    return (
                      <TableRow key={monitor.id} className="h-[6rem]">
                        <TableCell className="px-2 py-4">
                          <Link className="text-base font-medium text-foreground transition-colors hover:text-link" href={monitorDetailsHref(monitor.id, returnHref)} onClick={rememberListPosition}>{monitor.name}</Link>
                          <div className="mt-1 max-w-sm truncate text-sm text-muted-foreground" title={monitor.url}>{monitor.url}</div>
                        </TableCell>
                        <TableCell className="px-2 py-4"><StatusBadge status={monitor.status} /></TableCell>
                        <TableCell className="px-2 py-4"><div className="text-sm font-medium text-foreground">{check.label}</div><div className="mt-1 text-sm text-muted-foreground">{check.time}</div></TableCell>
                        <TableCell className="px-2 py-4 text-sm font-medium">{responseTime(monitor)}</TableCell>
                        <TableCell className="px-2 py-4 text-sm font-medium">{statusCode(monitor)}</TableCell>
                        <TableCell className="px-2 py-4 text-right"><MonitorActions monitor={monitor} returnHref={returnHref} onNavigate={rememberListPosition} onMonitorChange={replaceMonitor} onMonitorDelete={removeMonitor} /></TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>

            <div className="divide-y divide-border px-6 md:hidden" aria-label="All monitors">
              {data.items.map((monitor) => (
                <article className="flex flex-col gap-4 py-5" key={monitor.id}>
                  <div className="flex items-start justify-between gap-3"><div className="min-w-0"><Link className="font-semibold hover:text-link" href={monitorDetailsHref(monitor.id, returnHref)} onClick={rememberListPosition}>{monitor.name}</Link><p className="mt-1 break-all text-xs text-muted-foreground">{monitor.url}</p></div><StatusBadge status={monitor.status} /></div>
                  <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3"><div><dt className="text-xs text-muted-foreground">Latest check</dt><dd className="mt-1 text-sm font-medium">{latestCheck(monitor).label}</dd></div><div><dt className="text-xs text-muted-foreground">Response time</dt><dd className="mt-1 text-sm font-medium">{responseTime(monitor)}</dd></div><div><dt className="text-xs text-muted-foreground">Status code</dt><dd className="mt-1 text-sm font-medium">{statusCode(monitor)}</dd></div></dl>
                  <div className="flex justify-end"><MonitorActions monitor={monitor} returnHref={returnHref} onNavigate={rememberListPosition} onMonitorChange={replaceMonitor} onMonitorDelete={removeMonitor} /></div>
                </article>
              ))}
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-4 border-t px-6 py-5 sm:px-8 lg:flex-row lg:items-center lg:justify-between">
            <p className="text-sm text-muted-foreground">Showing {firstVisible} to {lastVisible} of {data.total} monitors</p>
            <div className="flex flex-wrap items-center gap-5">
              <div className="flex items-center gap-2">
                <Button variant="outline" size="icon-lg" type="button" disabled={data.page === 1} onClick={() => navigateToPage(Math.max(1, data.page - 1))} aria-label="Previous page"><ChevronLeftIcon /></Button>
                <Button className="border-primary/50 bg-primary/10 text-primary hover:bg-primary/15" variant="outline" size="icon-lg" type="button" aria-current="page">{data.page}</Button>
                <Button variant="outline" size="icon-lg" type="button" disabled={data.page === data.pages} onClick={() => navigateToPage(Math.min(data.pages, data.page + 1))} aria-label="Next page"><ChevronRightIcon /></Button>
              </div>
              <label className="sr-only" htmlFor="monitor-page-size">Rows per page</label>
              <select id="monitor-page-size" value={pageSize} onChange={(event) => navigateToPage(1, Number(event.target.value))} className="h-11 rounded-lg border border-input bg-card px-4 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50">
                <option value="5">5 / page</option><option value="10">10 / page</option><option value="25">25 / page</option>
              </select>
            </div>
          </CardFooter>
        </Card>
      ) : null}
    </main>
  )
}
