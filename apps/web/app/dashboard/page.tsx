import Link from "next/link"
import { ActivityIcon, PlusIcon } from "lucide-react"

import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

type PageProps = { searchParams: Promise<{ state?: string | string[] }> }

function normalizeState(value: string | string[] | undefined) {
  const state = Array.isArray(value) ? value[0] : value
  return state === "loading" || state === "empty" || state === "error" ? state : "ready"
}

export default async function DashboardPage({ searchParams }: PageProps) {
  const state = normalizeState((await searchParams).state)

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
      <header>
        <h1>Dashboard</h1>
        <p className="mt-1 text-muted-foreground">Current health across monitored endpoints.</p>
      </header>
      {state === "loading" ? <LoadingState label="Loading dashboard" count={3} className="lg:grid-cols-3" /> : null}
      {state === "empty" ? (
        <EmptyState
          title="No monitoring data yet"
          description="Dashboard health appears after you create a monitor and its first check completes."
          icon={<ActivityIcon className="size-7" />}
          action={<Button nativeButton={false} render={<Link href="/monitors/new" />}><PlusIcon data-icon="inline-start" />Create monitor</Button>}
        />
      ) : null}
      {state === "error" ? (
        <ErrorState
          title="Unable to load dashboard"
          description="Dashboard health could not be loaded. Retry the request."
          action={<Button variant="outline" nativeButton={false} render={<Link href="/dashboard" />}>Try again</Button>}
        />
      ) : null}
      {state === "ready" ? (
        <section className="grid gap-4 md:grid-cols-3" aria-label="Health summary">
          {[{ label: "Healthy", value: "8" }, { label: "Degraded", value: "1" }, { label: "Open incidents", value: "3" }].map((item) => (
            <Card key={item.label}>
              <CardHeader><CardDescription>{item.label}</CardDescription><CardTitle className="text-3xl">{item.value}</CardTitle></CardHeader>
              <CardContent className="text-muted-foreground">Updated from latest monitor checks.</CardContent>
            </Card>
          ))}
        </section>
      ) : null}
    </main>
  )
}
