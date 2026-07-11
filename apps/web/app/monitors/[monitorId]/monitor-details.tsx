"use client"

import Link from "next/link"
import {
  ArrowLeftIcon,
  Clock3Icon,
  PauseIcon,
  PencilIcon,
  PlayIcon,
  Trash2Icon,
} from "lucide-react"
import { useState } from "react"

import { StatusBadge, type MonitorStatus } from "@/components/status-badge"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
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

import type { Monitor } from "../monitor-data"

export type MonitorIncidentSummary = {
  id: string
  title: string
  status: string
  openedAt: string
  duration: string
  resolved: boolean
}

type RecentCheck = {
  id: string
  checkedAt: string
  status: "success" | "failed" | "paused"
  responseTime: string
  statusCode: string
  location: string
}

const configuration = [
  ["Method", "GET"],
  ["Interval", "5 minutes"],
  ["Timeout", "10 seconds"],
  ["Status range", "200-299"],
  ["Response threshold", "800 ms"],
  ["Uptime threshold", "99.9%"],
] as const

const baseChecks: RecentCheck[] = [
  { id: "chk-1015", checkedAt: "2:15 PM", status: "success", responseTime: "184 ms", statusCode: "200", location: "us-east-1" },
  { id: "chk-1014", checkedAt: "2:10 PM", status: "success", responseTime: "176 ms", statusCode: "200", location: "us-east-1" },
  { id: "chk-1013", checkedAt: "2:05 PM", status: "success", responseTime: "192 ms", statusCode: "200", location: "eu-west-1" },
  { id: "chk-1012", checkedAt: "2:00 PM", status: "success", responseTime: "211 ms", statusCode: "200", location: "us-west-2" },
  { id: "chk-1011", checkedAt: "1:55 PM", status: "success", responseTime: "189 ms", statusCode: "200", location: "us-east-1" },
]

function checksForMonitor(monitor: Monitor): RecentCheck[] {
  if (monitor.status === "down") {
    return [
      { id: "chk-2015", checkedAt: "2:15 PM", status: "failed", responseTime: monitor.responseTime, statusCode: "503", location: "us-east-1" },
      ...baseChecks.slice(1),
    ]
  }

  if (monitor.status === "paused") {
    return [
      { id: "chk-3015", checkedAt: "3 days ago", status: "paused", responseTime: "-", statusCode: "-", location: "us-east-1" },
      ...baseChecks.slice(1),
    ]
  }

  return baseChecks
}

function statusCopy(status: MonitorStatus) {
  if (status === "down") return "Latest check failed"
  if (status === "paused") return "Scheduled checks are paused"
  return "Latest check completed successfully"
}

function CheckBadge({ status }: { status: RecentCheck["status"] }) {
  if (status === "failed") {
    return <Badge variant="destructive">Failed</Badge>
  }

  if (status === "paused") {
    return <Badge className="bg-status-paused text-status-paused-foreground">Paused</Badge>
  }

  return <Badge className="bg-status-up text-status-up-foreground">Success</Badge>
}

function ResponseChart({ isDown }: { isDown: boolean }) {
  const points = isDown
    ? "0,178 56,166 112,171 168,152 224,160 280,148 336,153 392,142 448,149 504,134 560,140 616,126 672,132 728,42 800,54"
    : "0,178 56,166 112,171 168,152 224,160 280,148 336,153 392,142 448,149 504,134 560,140 616,126 672,132 728,119 800,128"

  return (
    <div
      className="overflow-hidden rounded-lg border bg-muted/20 p-3 sm:p-4"
      role="img"
      aria-label="Response time chart placeholder for the latest two hours"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>0 ms</span>
        <span>Threshold: 800 ms</span>
      </div>
      <svg className="h-56 w-full min-w-0" viewBox="0 0 800 220" preserveAspectRatio="none" aria-hidden="true">
        <line className="stroke-border" x1="0" x2="800" y1="40" y2="40" />
        <line className="stroke-border" x1="0" x2="800" y1="100" y2="100" />
        <line className="stroke-border" x1="0" x2="800" y1="160" y2="160" />
        <line className="stroke-status-down-foreground" strokeDasharray="7 7" x1="0" x2="800" y1="72" y2="72" />
        <polyline
          className="fill-none stroke-primary"
          points={points}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="3"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="mt-2 flex justify-between text-xs text-muted-foreground">
        <span>12:00</span><span>12:30</span><span>1:00</span><span>1:30</span><span>2:00</span>
      </div>
    </div>
  )
}

export function MonitorDetails({
  monitor,
  incidents,
}: {
  monitor: Monitor
  incidents: MonitorIncidentSummary[]
}) {
  const [status, setStatus] = useState<MonitorStatus>(monitor.status)
  const isPaused = status === "paused"
  const checks = checksForMonitor({ ...monitor, status })
  const latestCheck = checks[0]

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
      <div>
        <Link className={buttonVariants({ variant: "outline", size: "sm" })} href="/monitors">
          <ArrowLeftIcon data-icon="inline-start" />
          Back to monitors
        </Link>
      </div>

      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1>{monitor.name}</h1>
            <StatusBadge status={status} />
          </div>
          <a className="mt-2 block break-all text-sm text-primary hover:underline" href={monitor.url}>
            {monitor.url}
          </a>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" type="button">
            <PencilIcon data-icon="inline-start" />
            Edit
          </Button>
          <Button
            variant="outline"
            size="sm"
            type="button"
            onClick={() => setStatus((current) => current === "paused" ? "up" : "paused")}
          >
            {isPaused ? <PlayIcon data-icon="inline-start" /> : <PauseIcon data-icon="inline-start" />}
            {isPaused ? "Resume" : "Pause"}
          </Button>
          <Dialog>
            <DialogTrigger render={<Button variant="destructive" size="sm" type="button" />}>
              <Trash2Icon data-icon="inline-start" />
              Delete
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Delete {monitor.name}?</DialogTitle>
                <DialogDescription>This mock confirmation does not delete data or call a backend API.</DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <DialogClose render={<Button variant="outline" />}>Cancel</DialogClose>
                <DialogClose render={<Button variant="destructive" />}>Delete monitor</DialogClose>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </header>

      <Card className={cn(
        status === "up" && "border-l-4 border-l-status-up",
        status === "down" && "border-l-4 border-l-status-down",
        status === "paused" && "border-l-4 border-l-status-paused"
      )}>
        <CardHeader>
          <CardTitle>Current status</CardTitle>
          <CardDescription>{statusCopy(status)}</CardDescription>
          <CardAction><StatusBadge status={status} /></CardAction>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div><dt className="text-xs font-medium text-muted-foreground">Latest response time</dt><dd className="mt-1 text-2xl font-semibold">{latestCheck.responseTime}</dd></div>
            <div><dt className="text-xs font-medium text-muted-foreground">Status code</dt><dd className="mt-1 text-2xl font-semibold">{latestCheck.statusCode}</dd></div>
            <div><dt className="text-xs font-medium text-muted-foreground">Latest check</dt><dd className="mt-1 font-medium">{latestCheck.checkedAt}</dd></div>
            <div><dt className="text-xs font-medium text-muted-foreground">Location</dt><dd className="mt-1 font-medium">{latestCheck.location}</dd></div>
          </dl>
        </CardContent>
      </Card>

      <div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(20rem,0.85fr)]">
        <div className="flex min-w-0 flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Response time</CardTitle>
              <CardDescription>Latest two hours. Chart visualization is a mock placeholder.</CardDescription>
            </CardHeader>
            <CardContent><ResponseChart isDown={status === "down"} /></CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent checks</CardTitle>
              <CardDescription>Latest scheduled requests from mock monitor data.</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader><TableRow><TableHead>Time</TableHead><TableHead>Status</TableHead><TableHead>Response</TableHead><TableHead>Code</TableHead><TableHead>Location</TableHead></TableRow></TableHeader>
                <TableBody>
                  {checks.map((check) => (
                    <TableRow key={check.id}>
                      <TableCell>{check.checkedAt}</TableCell>
                      <TableCell><CheckBadge status={check.status} /></TableCell>
                      <TableCell>{check.responseTime}</TableCell>
                      <TableCell>{check.statusCode}</TableCell>
                      <TableCell>{check.location}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>

        <div className="flex min-w-0 flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Configuration</CardTitle>
              <CardDescription>Monitor request and alert thresholds.</CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="grid gap-4">
                {configuration.map(([label, value]) => (
                  <div className="flex items-center justify-between gap-4 border-b pb-3 last:border-b-0 last:pb-0" key={label}>
                    <dt className="text-muted-foreground">{label}</dt><dd className="text-right font-medium">{value}</dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Incident history</CardTitle>
              <CardDescription>Recent incidents associated with this monitor.</CardDescription>
            </CardHeader>
            <CardContent>
              {incidents.length > 0 ? (
                <ol className="grid gap-4">
                  {incidents.map((incident) => (
                    <li className="grid gap-2 border-l-2 border-border pl-4" key={incident.id}>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <Link className="font-medium hover:underline" href={`/monitors/incidents/${incident.id}`}>{incident.title}</Link>
                        <Badge className={incident.resolved ? "bg-status-up text-status-up-foreground" : "bg-status-down text-status-down-foreground"}>{incident.status}</Badge>
                      </div>
                      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                        <span>{incident.openedAt}</span><span className="inline-flex items-center gap-1"><Clock3Icon className="size-3" aria-hidden="true" />{incident.duration}</span>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : <p className="text-sm text-muted-foreground">No incidents recorded for this monitor.</p>}
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  )
}
