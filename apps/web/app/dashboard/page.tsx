import Link from "next/link"
import {
  ActivityIcon,
  AlertTriangleIcon,
  CircleCheckIcon,
  CircleHelpIcon,
  CirclePauseIcon,
  CircleXIcon,
  GaugeIcon,
  LayoutDashboardIcon,
  MonitorIcon,
  PlusIcon,
  SettingsIcon,
  ShieldAlertIcon,
} from "lucide-react"

import { getIncidents } from "@/app/monitors/incidents-data"
import { mockMonitors, type Monitor } from "@/app/monitors/monitor-data"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { StatusBadge, type MonitorStatus } from "@/components/status-badge"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

type PageProps = {
  searchParams: Promise<{ state?: string | string[] }>
}

type DashboardState = "ready" | "loading" | "empty" | "error"

type SummaryMetric = {
  label: string
  status: MonitorStatus
  icon: typeof CircleCheckIcon
}

const navigation = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboardIcon },
  { href: "/monitors", label: "Monitors", icon: MonitorIcon },
  { href: "/monitors?view=incidents", label: "Incidents", icon: ShieldAlertIcon },
  { href: "/settings", label: "Settings", icon: SettingsIcon },
]

const summaryMetrics: SummaryMetric[] = [
  { label: "Up", status: "up", icon: CircleCheckIcon },
  { label: "Down", status: "down", icon: CircleXIcon },
  { label: "Paused", status: "paused", icon: CirclePauseIcon },
  { label: "Unknown", status: "unknown", icon: CircleHelpIcon },
]

const responseBars = [32, 42, 28, 54, 43, 62, 47, 36, 50, 41, 30, 39]

function normalizeState(value: string | string[] | undefined): DashboardState {
  const state = Array.isArray(value) ? value[0] : value

  if (state === "loading" || state === "empty" || state === "error") {
    return state
  }

  return "ready"
}

function countByStatus(monitors: Monitor[], status: MonitorStatus) {
  return monitors.filter((monitor) => monitor.status === status).length
}

function AppNavigation({ mobile = false }: { mobile?: boolean }) {
  return (
    <nav aria-label="Application" className={cn(mobile ? "flex gap-1 overflow-x-auto px-4 py-2 lg:hidden" : "hidden lg:flex lg:flex-col lg:gap-1")}>
      {navigation.map((item) => {
        const Icon = item.icon
        const isCurrent = item.href === "/dashboard"

        return (
          <Link
            key={item.label}
            href={item.href}
            aria-current={isCurrent ? "page" : undefined}
            className={cn(
              "flex shrink-0 items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              isCurrent ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
          >
            <Icon className="size-4" aria-hidden="true" />
            {item.label}
          </Link>
        )
      })}
    </nav>
  )
}

function DashboardShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-muted/40">
      <header className="border-b bg-background lg:hidden">
        <div className="flex h-14 items-center justify-between px-4">
          <Link href="/dashboard" className="flex items-center gap-2 font-semibold">
            <span className="grid size-7 place-items-center rounded-md bg-primary text-primary-foreground"><ActivityIcon className="size-4" /></span>
            Uptime HQ
          </Link>
          <ThemeToggle />
        </div>
        <AppNavigation mobile />
      </header>
      <div className="mx-auto flex min-h-screen max-w-[1600px]">
        <aside className="hidden w-64 shrink-0 border-r bg-background px-3 py-5 lg:flex lg:flex-col">
          <Link href="/dashboard" className="mb-8 flex items-center gap-2 px-3 font-semibold">
            <span className="grid size-7 place-items-center rounded-md bg-primary text-primary-foreground"><ActivityIcon className="size-4" /></span>
            Uptime HQ
          </Link>
          <AppNavigation />
          <div className="mt-auto flex items-center justify-between rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">
            <span>Mock workspace</span>
            <ThemeToggle />
          </div>
        </aside>
        {children}
      </div>
    </div>
  )
}

function SummaryCards({ monitors }: { monitors: Monitor[] }) {
  return (
    <section aria-labelledby="monitor-summary" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <Card className="bg-primary text-primary-foreground ring-0">
        <CardHeader>
          <CardDescription className="text-primary-foreground/70">Monitors</CardDescription>
          <CardTitle id="monitor-summary" className="text-3xl font-semibold">{monitors.length}</CardTitle>
        </CardHeader>
      </Card>
      {summaryMetrics.map((metric) => {
        const Icon = metric.icon
        const total = countByStatus(monitors, metric.status)

        return (
          <Card key={metric.status} className="relative overflow-hidden">
            <CardHeader>
              <CardDescription>{metric.label}</CardDescription>
              <CardTitle className="text-3xl font-semibold">{total}</CardTitle>
            </CardHeader>
            <Icon className="absolute right-4 top-4 size-5 text-muted-foreground" aria-hidden="true" />
          </Card>
        )
      })}
    </section>
  )
}

function RecentMonitors({ monitors }: { monitors: Monitor[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent monitors</CardTitle>
        <CardDescription>Latest checks across monitored endpoints.</CardDescription>
      </CardHeader>
      <CardContent className="divide-y">
        {monitors.map((monitor) => (
          <div key={monitor.id} className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <Link href="/monitors" className="font-medium hover:underline">{monitor.name}</Link>
              <p className="mt-0.5 truncate text-sm text-muted-foreground">{monitor.url}</p>
            </div>
            <div className="flex items-center gap-4 sm:justify-end">
              <div className="text-right text-sm">
                <div className="font-medium">{monitor.responseTime}</div>
                <div className="text-muted-foreground">{monitor.lastCheck}</div>
              </div>
              <StatusBadge status={monitor.status} />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function ActiveIncidents() {
  const incidents = getIncidents("open")

  return (
    <Card>
      <CardHeader>
        <CardTitle>Active incidents</CardTitle>
        <CardDescription>{incidents.length} issue{incidents.length === 1 ? "" : "s"} need attention.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {incidents.map((incident) => (
          <Link key={incident.id} href={`/monitors/incidents/${incident.id}`} className="rounded-lg border border-status-down/30 bg-status-down/10 p-3 transition-colors hover:bg-status-down/20">
            <div className="flex items-start gap-3">
              <AlertTriangleIcon className="mt-0.5 size-4 shrink-0 text-status-down-foreground" aria-hidden="true" />
              <div className="min-w-0">
                <p className="font-medium">{incident.title}</p>
                <p className="mt-1 text-sm text-muted-foreground">{incident.monitorName} · {incident.duration}</p>
              </div>
            </div>
          </Link>
        ))}
      </CardContent>
    </Card>
  )
}

function ResponseTimeOverview() {
  return (
    <Card className="xl:col-span-2">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><GaugeIcon className="size-4 text-primary" aria-hidden="true" />Response time</CardTitle>
        <CardDescription>Placeholder overview · last 24 hours</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex h-44 items-end gap-2 rounded-lg border bg-muted/40 px-4 pb-4 pt-10" role="img" aria-label="Response-time placeholder showing twelve recent intervals">
          {responseBars.map((height, index) => (
            <div key={index} className="flex-1 rounded-sm bg-primary/70 transition-colors hover:bg-primary" style={{ height: `${height}%` }} />
          ))}
        </div>
        <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground"><span>24h ago</span><span>Median 184 ms</span><span>Now</span></div>
      </CardContent>
    </Card>
  )
}

function DashboardReady() {
  return (
    <div className="grid gap-6">
      <SummaryCards monitors={mockMonitors} />
      <div className="grid gap-6 xl:grid-cols-2">
        <RecentMonitors monitors={mockMonitors} />
        <ActiveIncidents />
        <ResponseTimeOverview />
      </div>
    </div>
  )
}

export default async function DashboardPage({ searchParams }: PageProps) {
  const requestedState = normalizeState((await searchParams).state)

  return (
    <DashboardShell>
      <main className="min-w-0 flex-1 px-4 py-7 sm:px-6 lg:px-8 lg:py-9">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
          <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="mb-1 text-sm font-medium text-primary">Service health</p>
              <h1>Dashboard</h1>
              <p className="mt-1 text-muted-foreground">Availability and latency across your monitored services.</p>
            </div>
            <Button nativeButton={false} className="w-full sm:w-auto" render={<Link href="/monitors/new" />}><PlusIcon data-icon="inline-start" />Create monitor</Button>
          </header>
          {requestedState === "loading" ? <LoadingState label="Loading dashboard" count={5} className="sm:grid-cols-2 xl:grid-cols-5" /> : null}
          {requestedState === "empty" ? <EmptyState title="No monitor data yet" description="No availability data exists because no monitor checks have completed. Create a monitor to begin tracking availability and response time." icon={<ActivityIcon className="size-7" />} action={<Button nativeButton={false} render={<Link href="/monitors/new" />}><PlusIcon data-icon="inline-start" />Create monitor</Button>} /> : null}
          {requestedState === "error" ? <ErrorState title="Unable to load dashboard" description="Dashboard monitoring data could not be loaded. Retry the request." action={<Button nativeButton={false} variant="outline" render={<Link href="/dashboard" />}>Try again</Button>} /> : null}
          {requestedState === "ready" ? <DashboardReady /> : null}
        </div>
      </main>
    </DashboardShell>
  )
}
