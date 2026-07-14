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
  SearchIcon,
  SlidersHorizontalIcon,
  Trash2Icon,
} from "lucide-react"
import { useState } from "react"

import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { StatusBadge, type MonitorStatus } from "@/components/status-badge"
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
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"
import { mockMonitors, type Monitor } from "./monitor-data"

export type MonitorViewState = "list" | "loading" | "empty" | "error"
type StatusFilter = "all" | MonitorStatus

function MonitorActions({ monitor, onToggleStatus }: { monitor: Monitor; onToggleStatus: (id: string) => void }) {
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
          <DialogDescription>Choose a monitor action. These controls use mock data only.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          <DialogClose render={<Button className="justify-start" variant="outline" size="lg" />}>
            <PencilIcon data-icon="inline-start" />Edit monitor
          </DialogClose>
          <DialogClose
            render={
              <Button
                className="justify-start"
                variant="outline"
                size="lg"
                onClick={() => onToggleStatus(monitor.id)}
              />
            }
          >
            {isPaused ? <PlayIcon data-icon="inline-start" /> : <PauseIcon data-icon="inline-start" />}
            {isPaused ? "Resume monitor" : "Pause monitor"}
          </DialogClose>
          <DialogClose render={<Button className="justify-start" variant="destructive" size="lg" />}>
            <Trash2Icon data-icon="inline-start" />Delete monitor
          </DialogClose>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function MonitorFilters({
  query,
  status,
  onQueryChange,
  onStatusChange,
}: {
  query: string
  status: StatusFilter
  onQueryChange: (value: string) => void
  onStatusChange: (value: StatusFilter) => void
}) {
  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="relative w-full lg:max-w-[37.5rem]">
        <label className="sr-only" htmlFor="monitor-search">Search monitors</label>
        <SearchIcon className="pointer-events-none absolute top-1/2 left-4 size-6 -translate-y-1/2 text-muted-foreground" strokeWidth={1.8} aria-hidden="true" />
        <Input
          id="monitor-search"
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search monitors..."
          className="h-[3.65rem] rounded-xl bg-card pl-13 text-base shadow-none"
        />
      </div>
      <div className="flex gap-3">
        <label className="sr-only" htmlFor="monitor-status">Filter by status</label>
        <select
          id="monitor-status"
          value={status}
          onChange={(event) => onStatusChange(event.target.value as StatusFilter)}
          className="h-[3.65rem] min-w-0 flex-1 rounded-xl border border-input bg-card px-4 text-base outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 sm:min-w-48"
        >
          <option value="all">All status</option>
          <option value="up">Up</option>
          <option value="down">Down</option>
          <option value="paused">Paused</option>
        </select>
        <Button className="size-[3.65rem] rounded-xl" variant="outline" size="icon-lg" type="button" aria-label="More filter options" title="More filter options">
          <SlidersHorizontalIcon className="size-5" />
        </Button>
      </div>
    </div>
  )
}

export function MonitorList({ viewState, initialQuery = "" }: { viewState: MonitorViewState; initialQuery?: string }) {
  const [monitors, setMonitors] = useState<Monitor[]>(mockMonitors)
  const [query, setQuery] = useState(initialQuery)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all")
  const [pageSize, setPageSize] = useState(10)
  const [page, setPage] = useState(1)

  const normalizedQuery = query.trim().toLowerCase()
  const filteredMonitors = monitors.filter((monitor) => {
    const matchesQuery = !normalizedQuery || `${monitor.name} ${monitor.url}`.toLowerCase().includes(normalizedQuery)
    const matchesStatus = statusFilter === "all" || monitor.status === statusFilter
    return matchesQuery && matchesStatus
  })
  const pageCount = Math.max(1, Math.ceil(filteredMonitors.length / pageSize))
  const currentPage = Math.min(page, pageCount)
  const firstVisible = filteredMonitors.length === 0 ? 0 : (currentPage - 1) * pageSize + 1
  const lastVisible = Math.min(currentPage * pageSize, filteredMonitors.length)
  const visibleMonitors = filteredMonitors.slice(firstVisible ? firstVisible - 1 : 0, lastVisible)

  function updateQuery(value: string) {
    setQuery(value)
    setPage(1)
  }

  function updateStatus(value: StatusFilter) {
    setStatusFilter(value)
    setPage(1)
  }

  function toggleMonitorStatus(id: string) {
    setMonitors((current) => current.map((monitor) => (
      monitor.id === id
        ? { ...monitor, status: monitor.status === "paused" ? "up" : "paused" }
        : monitor
    )))
  }

  return (
    <main className="relative mx-auto flex w-full max-w-[94rem] flex-col gap-5 overflow-hidden px-4 py-9 sm:px-6 lg:px-10 xl:px-12 xl:py-12">
      <header className="relative z-10 flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-[2.6rem] font-semibold tracking-[-0.045em] xl:text-[3rem]">Monitors</h1>
          <p className="mt-1.5 max-w-2xl text-base text-muted-foreground xl:text-lg">Track availability and response times for your endpoints.</p>
        </div>
        <Link className={cn(buttonVariants({ size: "lg" }), "h-14 rounded-xl px-6 text-base shadow-sm")} href="/monitors/new">
          <PlusIcon className="size-6" data-icon="inline-start" />
          Create monitor
        </Link>
      </header>

      {viewState === "loading" ? <LoadingState label="Loading monitors" count={3} /> : null}
      {viewState === "empty" ? <EmptyState title="No monitors yet" description="No endpoints are being checked. Create your first monitor to start tracking availability." action={<Button nativeButton={false} render={<Link href="/monitors/new" />}><PlusIcon data-icon="inline-start" />Create monitor</Button>} /> : null}
      {viewState === "error" ? <ErrorState title="Unable to load monitors" description="Monitor data could not be loaded. Retry the request." action={<Button variant="outline" type="button" onClick={() => window.location.reload()}>Try again</Button>} /> : null}

      {viewState === "list" ? (
        <>
          <div className="relative z-10 mt-5"><MonitorFilters query={query} status={statusFilter} onQueryChange={updateQuery} onStatusChange={updateStatus} /></div>

          <Card className="relative z-10 gap-0 overflow-hidden py-0">
            <CardHeader className="px-6 py-6 sm:px-8 sm:pt-7 sm:pb-4">
              <CardTitle className="text-xl">All monitors</CardTitle>
              <CardDescription className="text-base">Mock monitor data. No backend connection required.</CardDescription>
            </CardHeader>
            <CardContent className="px-0 sm:px-8">
              {visibleMonitors.length > 0 ? (
                <>
                  <div className="hidden overflow-x-auto md:block">
                    <Table className="min-w-[760px]">
                      <TableHeader>
                        <TableRow className="hover:bg-transparent">
                          <TableHead className="h-12 px-2 text-sm font-medium text-foreground">Monitor</TableHead>
                          <TableHead className="h-12 px-2 text-sm font-medium text-foreground">Status</TableHead>
                          <TableHead className="h-12 px-2 text-sm font-medium text-foreground">Latest check</TableHead>
                          <TableHead className="h-12 px-2 text-sm font-medium text-foreground">Response time</TableHead>
                          <TableHead className="h-12 px-2 text-right text-sm font-medium text-foreground">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {visibleMonitors.map((monitor) => (
                          <TableRow key={monitor.id} className="h-[6rem]">
                            <TableCell className="px-2 py-4">
                              <Link className="text-base font-medium text-foreground transition-colors hover:text-link" href={`/monitors/${monitor.id}`}>{monitor.name}</Link>
                              <div className="mt-1 max-w-sm truncate text-sm text-muted-foreground" title={monitor.url}>{monitor.url}</div>
                            </TableCell>
                            <TableCell className="px-2 py-4"><StatusBadge status={monitor.status} /></TableCell>
                            <TableCell className="px-2 py-4">
                              <div className="text-sm font-medium text-foreground">{monitor.lastCheck}</div>
                              <div className="mt-1 text-sm text-muted-foreground">{monitor.lastCheckTime}</div>
                            </TableCell>
                            <TableCell className="px-2 py-4 text-sm font-medium">{monitor.responseTime}</TableCell>
                            <TableCell className="px-2 py-4 text-right"><MonitorActions monitor={monitor} onToggleStatus={toggleMonitorStatus} /></TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>

                  <div className="divide-y divide-border md:hidden" aria-label="All monitors">
                    {visibleMonitors.map((monitor) => (
                      <article className="flex flex-col gap-4 py-5" key={monitor.id}>
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <Link className="font-semibold hover:text-link" href={`/monitors/${monitor.id}`}>{monitor.name}</Link>
                            <p className="mt-1 break-all text-xs text-muted-foreground">{monitor.url}</p>
                          </div>
                          <StatusBadge status={monitor.status} />
                        </div>
                        <dl className="grid grid-cols-2 gap-4">
                          <div><dt className="text-xs text-muted-foreground">Latest check</dt><dd className="mt-1 text-sm font-medium">{monitor.lastCheck}</dd></div>
                          <div><dt className="text-xs text-muted-foreground">Response time</dt><dd className="mt-1 text-sm font-medium">{monitor.responseTime}</dd></div>
                        </dl>
                        <div className="flex justify-end"><MonitorActions monitor={monitor} onToggleStatus={toggleMonitorStatus} /></div>
                      </article>
                    ))}
                  </div>
                </>
              ) : (
                <div className="flex min-h-56 flex-col items-center justify-center text-center">
                  <SearchIcon className="size-8 text-muted-foreground" aria-hidden="true" />
                  <h2 className="mt-4 text-base">No matching monitors</h2>
                  <p className="mt-1 text-sm text-muted-foreground">Try another search or status filter.</p>
                </div>
              )}
            </CardContent>
            <CardFooter className="flex flex-col gap-4 border-t px-6 py-5 sm:px-8 lg:flex-row lg:items-center lg:justify-between">
              <p className="text-sm text-muted-foreground">Showing {firstVisible} to {lastVisible} of {filteredMonitors.length} monitors</p>
              <div className="flex flex-wrap items-center gap-5">
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="icon-lg" type="button" disabled={currentPage === 1} onClick={() => setPage((value) => Math.max(1, value - 1))} aria-label="Previous page"><ChevronLeftIcon /></Button>
                  <Button className="border-primary/50 bg-primary/10 text-primary hover:bg-primary/15" variant="outline" size="icon-lg" type="button" aria-current="page">{currentPage}</Button>
                  <Button variant="outline" size="icon-lg" type="button" disabled={currentPage === pageCount} onClick={() => setPage((value) => Math.min(pageCount, value + 1))} aria-label="Next page"><ChevronRightIcon /></Button>
                </div>
                <label className="sr-only" htmlFor="monitor-page-size">Rows per page</label>
                <select
                  id="monitor-page-size"
                  value={pageSize}
                  onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1) }}
                  className="h-11 rounded-lg border border-input bg-card px-4 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  <option value="5">5 / page</option>
                  <option value="10">10 / page</option>
                  <option value="25">25 / page</option>
                </select>
              </div>
            </CardFooter>
          </Card>
        </>
      ) : null}
    </main>
  )
}
