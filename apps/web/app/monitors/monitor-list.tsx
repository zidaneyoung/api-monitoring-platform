"use client"

import Link from "next/link"
import {
  PauseIcon,
  PencilIcon,
  PlayIcon,
  PlusIcon,
  Trash2Icon,
} from "lucide-react"
import { useState } from "react"

import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { StatusBadge } from "@/components/status-badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"
import { mockMonitors, type Monitor } from "./monitor-data"

export type MonitorViewState = "list" | "loading" | "empty" | "error"

function MonitorActions({ monitor, onToggleStatus }: { monitor: Monitor; onToggleStatus: (id: string) => void }) {
  const isPaused = monitor.status === "paused"

  return (
    <div className="flex items-center justify-end gap-1">
      <Button variant="ghost" size="icon" type="button" aria-label={`Edit ${monitor.name}`} title={`Edit ${monitor.name}`}>
        <PencilIcon />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        type="button"
        aria-label={`${isPaused ? "Resume" : "Pause"} ${monitor.name}`}
        title={`${isPaused ? "Resume" : "Pause"} ${monitor.name}`}
        onClick={() => onToggleStatus(monitor.id)}
      >
        {isPaused ? <PlayIcon /> : <PauseIcon />}
      </Button>
      <Dialog>
        <DialogTrigger
          render={
            <Button
              variant="ghost"
              size="icon"
              type="button"
              aria-label={`Delete ${monitor.name}`}
              title={`Delete ${monitor.name}`}
            />
          }
        >
          <Trash2Icon />
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete {monitor.name}?</DialogTitle>
            <DialogDescription>
              This mock confirmation does not delete data or call a backend API.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" />}>Cancel</DialogClose>
            <DialogClose render={<Button variant="destructive" />}>Delete monitor</DialogClose>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export function MonitorList({ viewState }: { viewState: MonitorViewState }) {
  const [monitors, setMonitors] = useState<Monitor[]>(mockMonitors)

  function toggleMonitorStatus(id: string) {
    setMonitors((current) =>
      current.map((monitor) =>
        monitor.id === id
          ? { ...monitor, status: monitor.status === "paused" ? "up" : "paused" }
          : monitor
      )
    )
  }

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1>Monitors</h1>
          <p className="mt-1 text-muted-foreground">Track availability and response times for your endpoints.</p>
        </div>
        <Button nativeButton={false} render={<Link href="/monitors/new" />} className="w-full sm:w-auto">
          <PlusIcon data-icon="inline-start" />
          Create monitor
        </Button>
      </header>

      {viewState === "loading" ? <LoadingState label="Loading monitors" count={3} className="xl:grid-cols-3" /> : null}
      {viewState === "empty" ? (
        <EmptyState
          title="No monitors yet"
          description="No endpoints are being checked. Create your first monitor to start tracking availability."
          action={<Link className={buttonVariants()} href="/monitors/new"><PlusIcon data-icon="inline-start" />Create monitor</Link>}
        />
      ) : null}
      {viewState === "error" ? (
        <ErrorState title="Unable to load monitors" description="Monitor data could not be loaded. Retry the request." action={<Button variant="outline" type="button" onClick={() => window.location.reload()}>Try again</Button>} />
      ) : null}
      {viewState === "list" ? (
        <>
          <Card className="hidden md:flex">
            <CardHeader>
              <CardTitle>All monitors</CardTitle>
              <CardDescription>Mock monitor data. No backend connection required.</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Monitor</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Latest check</TableHead>
                    <TableHead>Response time</TableHead>
                    <TableHead className="text-right"><span className="sr-only">Actions</span></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {monitors.map((monitor) => (
                    <TableRow
                      key={monitor.id}
                      className={cn(monitor.status === "paused" && "border-l-4 border-l-status-paused bg-status-paused/10")}
                    >
                      <TableCell>
                        <Link className="font-medium hover:underline" href={`/monitors/${monitor.id}`}>
                          {monitor.name}
                        </Link>
                        <div className="max-w-xs truncate text-muted-foreground" title={monitor.url}>{monitor.url}</div>
                      </TableCell>
                      <TableCell><StatusBadge status={monitor.status} /></TableCell>
                      <TableCell>{monitor.lastCheck}</TableCell>
                      <TableCell>{monitor.responseTime}</TableCell>
                      <TableCell><MonitorActions monitor={monitor} onToggleStatus={toggleMonitorStatus} /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <section className="grid gap-4 md:hidden" aria-label="All monitors">
            {monitors.map((monitor) => (
              <Card
                key={monitor.id}
                className={cn(monitor.status === "paused" && "border-l-4 border-l-status-paused bg-status-paused/10")}
              >
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <CardTitle>
                        <Link className="hover:underline" href={`/monitors/${monitor.id}`}>
                          {monitor.name}
                        </Link>
                      </CardTitle>
                      <CardDescription className="mt-1 break-all">{monitor.url}</CardDescription>
                    </div>
                    <StatusBadge status={monitor.status} />
                  </div>
                </CardHeader>
                <CardContent>
                  <dl className="grid grid-cols-2 gap-4">
                    <div>
                      <dt className="text-xs font-medium text-muted-foreground">Latest check</dt>
                      <dd className="mt-1">{monitor.lastCheck}</dd>
                    </div>
                    <div>
                      <dt className="text-xs font-medium text-muted-foreground">Response time</dt>
                      <dd className="mt-1">{monitor.responseTime}</dd>
                    </div>
                  </dl>
                </CardContent>
                <CardFooter className="justify-end">
                  <MonitorActions monitor={monitor} onToggleStatus={toggleMonitorStatus} />
                </CardFooter>
              </Card>
            ))}
          </section>
        </>
      ) : null}
    </main>
  )
}
