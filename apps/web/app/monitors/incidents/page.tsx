import {
  AlertTriangleIcon,
  InboxIcon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

import { getIncidents } from "../incidents-data"
import { IncidentHistoryClient } from "./incident-history-client"

type PageProps = {
  searchParams: Promise<{ state?: string }>
}
function normalizeState(value: string | string[] | undefined) {
  const state = Array.isArray(value) ? value[0] : value

  if (state === "loading" || state === "empty" || state === "error") {
    return state
  }

  return "ready"
}

function LoadingState() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {Array.from({ length: 2 }).map((_, index) => (
        <Card key={index}>
          <CardHeader>
            <div className="h-5 w-40 rounded-md bg-muted" />
            <div className="h-4 w-56 rounded-md bg-muted" />
          </CardHeader>
          <CardContent className="grid gap-3">
            <div className="h-28 rounded-lg bg-muted" />
            <div className="h-28 rounded-lg bg-muted" />
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function EmptyState() {
  return (
    <Card className="items-center py-12 text-center">
      <CardContent className="flex max-w-md flex-col items-center gap-3">
        <InboxIcon className="size-10 text-muted-foreground" aria-hidden="true" />
        <div>
          <h2>No incidents yet</h2>
          <p className="mt-1 text-muted-foreground">Open and resolved incidents will appear here once monitors detect an outage.</p>
        </div>
      </CardContent>
    </Card>
  )
}

function ErrorState() {
  return (
    <Card className="border-destructive/40 py-12 text-center">
      <CardContent className="flex flex-col items-center gap-3">
        <AlertTriangleIcon className="size-10 text-destructive" aria-hidden="true" />
        <div>
          <h2>Unable to display incident history</h2>
          <p className="mt-1 text-muted-foreground">Something went wrong while preparing this mock view. Try again.</p>
        </div>
        <Button variant="outline" type="button">Try again</Button>
      </CardContent>
    </Card>
  )
}

export default async function MonitorsPage({ searchParams }: PageProps) {
  const requestedState = normalizeState((await searchParams).state)
  const openIncidents = getIncidents("open")
  const resolvedIncidents = getIncidents("resolved")

  if (requestedState === "ready") {
    return <IncidentHistoryClient openIncidents={openIncidents} resolvedIncidents={resolvedIncidents} />
  }

  return (
    <main className="incident-history-page min-h-[calc(100svh-3.5rem)] px-4 py-7 sm:px-6 lg:px-8 xl:px-14 xl:py-8">
      <div className="mx-auto w-full max-w-[86rem]">
        {requestedState === "loading" ? <LoadingState /> : null}
        {requestedState === "empty" ? <EmptyState /> : null}
        {requestedState === "error" ? <ErrorState /> : null}
      </div>
    </main>
  )
}
