"use client"

import Link from "next/link"
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  Clock3Icon,
  PauseIcon,
  PencilIcon,
  PlayIcon,
  Trash2Icon,
} from "lucide-react"
import { useState } from "react"

import { StatusBadge, type MonitorStatus } from "@/components/status-badge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
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
  ["Status range", "200–299"],
  ["Response threshold", "800 ms"],
  ["Uptime threshold", "99.9%"],
] as const

const baseChecks: RecentCheck[] = [
  { id: "chk-1015", checkedAt: "2:15 PM", status: "success", responseTime: "184 ms", statusCode: "200", location: "us-east-1" },
  { id: "chk-1014", checkedAt: "2:10 PM", status: "success", responseTime: "176 ms", statusCode: "200", location: "us-east-1" },
  { id: "chk-1013", checkedAt: "2:05 PM", status: "success", responseTime: "192 ms", statusCode: "200", location: "us-west-1" },
  { id: "chk-1012", checkedAt: "2:00 PM", status: "success", responseTime: "211 ms", statusCode: "200", location: "us-west-2" },
  { id: "chk-1011", checkedAt: "1:55 PM", status: "success", responseTime: "169 ms", statusCode: "200", location: "us-east-1" },
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

function CheckBadge({ status }: { status: RecentCheck["status"] }) {
  if (status === "failed") return <Badge variant="destructive">Failed</Badge>
  if (status === "paused") return <Badge variant="outline" className="border-status-paused-foreground/35 bg-status-paused text-status-paused-foreground">Paused</Badge>
  return <Badge variant="outline" className="border-status-up-foreground/35 bg-status-up text-status-up-foreground">Success</Badge>
}

function ResponseChart({ isDown }: { isDown: boolean }) {
  const points = isDown
    ? "0,164 55,152 110,157 165,142 220,149 275,136 330,143 385,130 440,137 495,120 550,127 605,112 660,119 715,40 800,52"
    : "0,164 55,152 110,157 165,142 220,149 275,136 330,143 385,130 440,137 495,120 550,127 605,112 660,119 715,104 800,114"

  return (
    <div className="relative overflow-hidden rounded-xl border bg-background/25 px-4 pt-3 pb-3" role="img" aria-label="Response time chart placeholder for the latest two hours with an 800 millisecond threshold">
      <div className="flex justify-end text-xs text-muted-foreground">Threshold: 800 ms</div>
      <svg className="mt-1 h-36 w-full sm:h-40 xl:h-44" viewBox="0 0 800 190" preserveAspectRatio="none" aria-hidden="true">
        <line className="stroke-status-down-foreground" strokeDasharray="7 6" x1="0" x2="800" y1="60" y2="60" strokeWidth="1.5" />
        <polyline className="fill-none stroke-chart-line" points={points} strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.25" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="-mt-2 flex justify-between text-[11px] text-muted-foreground sm:text-xs">
        <span>0 ms</span><span>12:30</span><span>1:00</span><span>1:30</span><span>2:00</span>
      </div>
    </div>
  )
}

function SummaryCard({ label, value, valueClassName }: { label: string; value: React.ReactNode; valueClassName?: string }) {
  return (
    <Card className="min-h-28 gap-0 py-0 sm:min-h-32">
      <CardContent className="flex h-full min-h-28 flex-col items-center justify-center px-4 py-5 text-center sm:min-h-32">
        <dt className="text-sm font-medium text-muted-foreground">{label}</dt>
        <dd className={cn("mt-3 truncate text-[1.75rem] font-semibold tracking-[-0.03em]", valueClassName)}>{value}</dd>
      </CardContent>
    </Card>
  )
}

function incidentTone(incident: MonitorIncidentSummary) {
  if (incident.resolved) return "border-status-up-foreground/35 bg-status-up text-status-up-foreground"
  if (incident.status.toLowerCase().includes("mitigat")) return "border-status-paused-foreground/35 bg-status-paused text-status-paused-foreground"
  return "border-status-down-foreground/35 bg-status-down text-status-down-foreground"
}

export function MonitorDetails({ monitor, incidents }: { monitor: Monitor; incidents: MonitorIncidentSummary[] }) {
  const [status, setStatus] = useState<MonitorStatus>(monitor.status)
  const isPaused = status === "paused"
  const checks = checksForMonitor({ ...monitor, status })
  const latestCheck = checks[0]
  const statusLabel = status === "up" ? "Up" : status === "down" ? "Down" : "Paused"

  return (
    <main className="mx-auto flex w-full max-w-[94rem] flex-col gap-4 px-4 py-6 sm:px-6 lg:px-8 xl:px-11 xl:py-7">
      <Link className="inline-flex w-fit items-center gap-2 text-sm font-medium text-foreground transition-colors hover:text-link focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50" href="/monitors">
        <ArrowLeftIcon className="size-4" aria-hidden="true" />
        Back to monitors
      </Link>

      <header className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-4">
            <h1 className="text-[2.25rem] font-semibold tracking-[-0.045em] sm:text-[2.45rem]">{monitor.name}</h1>
            <StatusBadge status={status} className="px-3 py-1 text-base" />
          </div>
          <a className="mt-1 block break-all text-base font-semibold text-link hover:underline" href={monitor.url}>{monitor.url}</a>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button className="h-10 px-4" variant="outline" size="lg" type="button"><PencilIcon data-icon="inline-start" />Edit</Button>
          <Button className="h-10 px-4" variant="outline" size="lg" type="button" onClick={() => setStatus((current) => current === "paused" ? "up" : "paused")}>
            {isPaused ? <PlayIcon data-icon="inline-start" /> : <PauseIcon data-icon="inline-start" />}
            {isPaused ? "Resume" : "Pause"}
          </Button>
          <Dialog>
            <DialogTrigger render={<Button className="h-10 px-4" variant="destructive" size="lg" type="button" />}>
              <Trash2Icon data-icon="inline-start" />Delete
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

      <dl className="mt-1 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <SummaryCard
          label="Current status"
          value={statusLabel}
          valueClassName={status === "up" ? "text-status-up-foreground" : status === "down" ? "text-status-down-foreground" : "text-status-paused-foreground"}
        />
        <SummaryCard label="Latest response time" value={latestCheck.responseTime} />
        <SummaryCard label="Status code" value={latestCheck.statusCode} />
        <SummaryCard label="Latest check" value={latestCheck.checkedAt} />
        <SummaryCard label="Location" value={latestCheck.location} />
      </dl>

      <div className="mt-1 grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(20rem,1fr)]">
        <Card className="gap-0 py-0">
          <CardHeader className="px-5 pt-5 pb-3 sm:px-6">
            <CardTitle>Response time</CardTitle>
            <CardDescription>Latest two hours. Chart visualization is a mock placeholder.</CardDescription>
          </CardHeader>
          <CardContent className="px-5 pb-5 sm:px-6"><ResponseChart isDown={status === "down"} /></CardContent>
        </Card>

        <Card className="gap-0 py-0">
          <CardHeader className="px-5 pt-5 pb-2 sm:px-6">
            <CardTitle>Configuration</CardTitle>
            <CardDescription>Monitor request and alert thresholds.</CardDescription>
          </CardHeader>
          <CardContent className="px-5 pb-2 sm:px-6">
            <dl>
              {configuration.map(([label, value]) => (
                <div className="flex items-center justify-between gap-4 border-b py-2.5 last:border-b-0" key={label}>
                  <dt className="text-sm text-muted-foreground">{label}</dt><dd className="text-right text-sm font-semibold">{value}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>

        <Card id="recent-checks" className="min-w-0 gap-0 py-0">
          <CardHeader className="px-5 pt-5 pb-2 sm:px-6">
            <CardTitle>Recent checks</CardTitle>
            <CardDescription>Latest scheduled requests from mock monitor data.</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto px-5 pb-5 sm:px-6">
            <Table className="min-w-[620px]">
              <TableHeader><TableRow className="hover:bg-transparent"><TableHead className="h-10 px-0 text-xs font-semibold text-foreground">Time</TableHead><TableHead className="h-10 px-3 text-xs font-semibold text-foreground">Status</TableHead><TableHead className="h-10 px-3 text-xs font-semibold text-foreground">Response</TableHead><TableHead className="h-10 px-3 text-xs font-semibold text-foreground">Code</TableHead><TableHead className="h-10 px-0 text-xs font-semibold text-foreground">Location</TableHead></TableRow></TableHeader>
              <TableBody>
                {checks.map((check) => (
                  <TableRow key={check.id} className="h-9">
                    <TableCell className="px-0 py-1 text-sm">{check.checkedAt}</TableCell>
                    <TableCell className="px-3 py-1"><CheckBadge status={check.status} /></TableCell>
                    <TableCell className="px-3 py-1 text-sm font-medium">{check.responseTime}</TableCell>
                    <TableCell className="px-3 py-1 text-sm">{check.statusCode}</TableCell>
                    <TableCell className="px-0 py-1 text-sm">{check.location}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Link className="mt-5 inline-flex items-center gap-3 text-sm font-semibold text-link hover:underline" href={`?view=checks`}>
              View all checks <ArrowRightIcon className="size-4" aria-hidden="true" />
            </Link>
          </CardContent>
        </Card>

        <Card className="gap-0 py-0">
          <CardHeader className="px-5 pt-5 pb-3 sm:px-6">
            <CardTitle>Incident history</CardTitle>
            <CardDescription>Recent incidents associated with this monitor.</CardDescription>
          </CardHeader>
          <CardContent className="px-5 pb-5 sm:px-6">
            {incidents.length > 0 ? (
              <ol className="flex flex-col gap-4">
                {incidents.map((incident) => (
                  <li className="grid gap-1" key={incident.id}>
                    <div className="flex items-center justify-between gap-3">
                      <Link className="min-w-0 truncate text-sm font-semibold transition-colors hover:text-link" href={`/monitors/incidents/${incident.id}`}>{incident.title}</Link>
                      <Badge variant="outline" className={incidentTone(incident)}>{incident.status}</Badge>
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                      <span>{incident.openedAt}</span><span className="inline-flex items-center gap-1"><Clock3Icon className="size-3.5" aria-hidden="true" />{incident.duration}</span>
                    </div>
                  </li>
                ))}
              </ol>
            ) : <p className="text-sm text-muted-foreground">No incidents recorded for this monitor.</p>}
            <Link className="mt-5 inline-flex items-center gap-3 text-sm font-semibold text-link hover:underline" href="/monitors/incidents">
              View all incidents <ArrowRightIcon className="size-4" aria-hidden="true" />
            </Link>
          </CardContent>
        </Card>
      </div>
    </main>
  )
}
