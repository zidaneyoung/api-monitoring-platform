import Link from "next/link"
import { PlusIcon } from "lucide-react"

import { Button } from "@/components/ui/button"

import { ActiveIncidents } from "./active-incidents"
import { MonitorSummary } from "./monitor-summary"
import { RecentMonitors } from "./recent-monitors"

function DashboardShell({ children }: { children: React.ReactNode }) {
  return <div className="min-h-full bg-muted/40">{children}</div>
}

function DashboardData() {
  return (
    <div className="grid gap-6">
      <MonitorSummary />
      <div className="grid gap-6 xl:grid-cols-2">
        <RecentMonitors />
        <ActiveIncidents />
      </div>
    </div>
  )
}

export default function DashboardPage() {
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
          <DashboardData />
        </div>
      </main>
    </DashboardShell>
  )
}
