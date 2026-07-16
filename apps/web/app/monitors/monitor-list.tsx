"use client"

import Link from "next/link"
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  MoreVerticalIcon,
  PauseIcon,
  PencilIcon,
  PlayIcon,
  PlusIcon,
  Trash2Icon,
} from "lucide-react"
import { useEffect, useState } from "react"

import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { StatusBadge } from "@/components/status-badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"
import { listMonitors, type MonitorDto, type MonitorListDto } from "@/lib/monitor-api"


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

function MonitorActions({ monitor }: { monitor: MonitorDto }) {
  const isPaused = monitor.status === "paused"

  return (
    <Dialog>
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
          <DialogDescription>Monitor mutations are not available yet.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          <Link className={cn(buttonVariants({ variant: "outline", size: "lg" }), "justify-start")} href={`/monitors/${monitor.id}/edit`}>
            <PencilIcon data-icon="inline-start" />Edit monitor
          </Link>
          <DialogClose render={<Button className="justify-start" variant="outline" size="lg" disabled />}>
            {isPaused ? <PlayIcon data-icon="inline-start" /> : <PauseIcon data-icon="inline-start" />}
            {isPaused ? "Resume monitor" : "Pause monitor"}
          </DialogClose>
          <DialogClose render={<Button className="justify-start" variant="destructive" size="lg" disabled />}>
            <Trash2Icon data-icon="inline-start" />Delete monitor
          </DialogClose>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export function MonitorList() {
  const [pageSize, setPageSize] = useState(10)
  const [page, setPage] = useState(1)
  const [requestVersion, setRequestVersion] = useState(0)
  const [state, setState] = useState<ListState>({ type: "loading" })

  useEffect(() => {
    let cancelled = false
    void listMonitors(page, pageSize).then((outcome) => {
      if (cancelled) return
      if (outcome.type === "success") {
        if (page > outcome.data.pages) {
          setState({ type: "loading" })
          setPage(outcome.data.pages)
          return
        }
        setState({ type: "ready", data: outcome.data })
        return
      }
      setState({ type: "error" })
    })
    return () => { cancelled = true }
  }, [page, pageSize, requestVersion])

  const data = state.type === "ready" ? state.data : null
  const firstVisible = data && data.total > 0 ? (data.page - 1) * data.page_size + 1 : 0
  const lastVisible = data ? Math.min(data.page * data.page_size, data.total) : 0

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
                          <Link className="text-base font-medium text-foreground transition-colors hover:text-link" href={`/monitors/${monitor.id}`}>{monitor.name}</Link>
                          <div className="mt-1 max-w-sm truncate text-sm text-muted-foreground" title={monitor.url}>{monitor.url}</div>
                        </TableCell>
                        <TableCell className="px-2 py-4"><StatusBadge status={monitor.status} /></TableCell>
                        <TableCell className="px-2 py-4"><div className="text-sm font-medium text-foreground">{check.label}</div><div className="mt-1 text-sm text-muted-foreground">{check.time}</div></TableCell>
                        <TableCell className="px-2 py-4 text-sm font-medium">{responseTime(monitor)}</TableCell>
                        <TableCell className="px-2 py-4 text-sm font-medium">{statusCode(monitor)}</TableCell>
                        <TableCell className="px-2 py-4 text-right"><MonitorActions monitor={monitor} /></TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>

            <div className="divide-y divide-border md:hidden" aria-label="All monitors">
              {data.items.map((monitor) => (
                <article className="flex flex-col gap-4 py-5" key={monitor.id}>
                  <div className="flex items-start justify-between gap-3"><div className="min-w-0"><Link className="font-semibold hover:text-link" href={`/monitors/${monitor.id}`}>{monitor.name}</Link><p className="mt-1 break-all text-xs text-muted-foreground">{monitor.url}</p></div><StatusBadge status={monitor.status} /></div>
                  <dl className="grid grid-cols-3 gap-4"><div><dt className="text-xs text-muted-foreground">Latest check</dt><dd className="mt-1 text-sm font-medium">{latestCheck(monitor).label}</dd></div><div><dt className="text-xs text-muted-foreground">Response time</dt><dd className="mt-1 text-sm font-medium">{responseTime(monitor)}</dd></div><div><dt className="text-xs text-muted-foreground">Status code</dt><dd className="mt-1 text-sm font-medium">{statusCode(monitor)}</dd></div></dl>
                  <div className="flex justify-end"><MonitorActions monitor={monitor} /></div>
                </article>
              ))}
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-4 border-t px-6 py-5 sm:px-8 lg:flex-row lg:items-center lg:justify-between">
            <p className="text-sm text-muted-foreground">Showing {firstVisible} to {lastVisible} of {data.total} monitors</p>
            <div className="flex flex-wrap items-center gap-5">
              <div className="flex items-center gap-2">
                <Button variant="outline" size="icon-lg" type="button" disabled={data.page === 1} onClick={() => { setState({ type: "loading" }); setPage((value) => Math.max(1, value - 1)) }} aria-label="Previous page"><ChevronLeftIcon /></Button>
                <Button className="border-primary/50 bg-primary/10 text-primary hover:bg-primary/15" variant="outline" size="icon-lg" type="button" aria-current="page">{data.page}</Button>
                <Button variant="outline" size="icon-lg" type="button" disabled={data.page === data.pages} onClick={() => { setState({ type: "loading" }); setPage((value) => Math.min(data.pages, value + 1)) }} aria-label="Next page"><ChevronRightIcon /></Button>
              </div>
              <label className="sr-only" htmlFor="monitor-page-size">Rows per page</label>
              <select id="monitor-page-size" value={pageSize} onChange={(event) => { setState({ type: "loading" }); setPageSize(Number(event.target.value)); setPage(1) }} className="h-11 rounded-lg border border-input bg-card px-4 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50">
                <option value="5">5 / page</option><option value="10">10 / page</option><option value="25">25 / page</option>
              </select>
            </div>
          </CardFooter>
        </Card>
      ) : null}
    </main>
  )
}
