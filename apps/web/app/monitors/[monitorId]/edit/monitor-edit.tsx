"use client"

import Link from "next/link"
import { ArrowLeftIcon } from "lucide-react"
import { useEffect, useState } from "react"

import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { getMonitor, type MonitorDto } from "@/lib/monitor-api"
import { monitorDetailsHref, monitorListHref } from "@/lib/monitor-navigation"

import { MonitorForm } from "../../new/monitor-form"


type EditState =
  | { type: "loading"; monitorId: string }
  | { type: "not_found"; monitorId: string }
  | { type: "error"; monitorId: string }
  | { type: "ready"; monitorId: string; monitor: MonitorDto }

function LoadingEdit() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-5 px-4 py-8 sm:px-6 lg:px-8" aria-busy="true">
      <span className="sr-only">Loading monitor configuration</span>
      <div className="h-10 w-44 animate-pulse rounded-md bg-muted" />
      <div className="h-14 w-72 animate-pulse rounded-md bg-muted" />
      <div className="h-96 animate-pulse rounded-xl bg-muted" />
    </main>
  )
}

function EditMessage({
  monitorId,
  returnHref,
  retry,
}: {
  monitorId: string
  returnHref: string
  retry?: () => void
}) {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 py-8 sm:px-6 lg:px-8">
      <Card className="items-center py-12 text-center">
        <CardContent className="flex max-w-lg flex-col items-center gap-3">
          <h1>{retry ? "Unable to load monitor" : "Monitor not found"}</h1>
          <p className="text-muted-foreground">
            {retry
              ? "The current monitor configuration could not be loaded. Try again."
              : "This monitor does not exist or is not available to your account."}
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {retry ? <Button variant="outline" type="button" onClick={retry}>Try again</Button> : null}
            <Link className={buttonVariants({ variant: "outline" })} href={retry ? monitorDetailsHref(monitorId, returnHref) : returnHref}>Back</Link>
          </div>
        </CardContent>
      </Card>
    </main>
  )
}

export function MonitorEdit({
  monitorId,
  returnHref = monitorListHref(),
}: {
  monitorId: string
  returnHref?: string
}) {
  const [requestVersion, setRequestVersion] = useState(0)
  const [state, setState] = useState<EditState>({ type: "loading", monitorId })
  const detailsHref = monitorDetailsHref(monitorId, returnHref)

  useEffect(() => {
    let cancelled = false
    void getMonitor(monitorId).then((outcome) => {
      if (cancelled) return
      if (outcome.type === "success") setState({ type: "ready", monitorId, monitor: outcome.data })
      else if (outcome.type === "not_found") setState({ type: "not_found", monitorId })
      else setState({ type: "error", monitorId })
    })
    return () => { cancelled = true }
  }, [monitorId, requestVersion])

  if (state.type === "loading" || state.monitorId !== monitorId) return <LoadingEdit />
  if (state.type === "not_found") return <EditMessage monitorId={monitorId} returnHref={returnHref} />
  if (state.type === "error") return <EditMessage monitorId={monitorId} returnHref={returnHref} retry={() => { setState({ type: "loading", monitorId }); setRequestVersion((value) => value + 1) }} />

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-5 px-4 py-8 sm:px-6 lg:px-8">
      <Link className={buttonVariants({ variant: "outline", size: "sm", className: "w-fit" })} href={detailsHref}>
        <ArrowLeftIcon data-icon="inline-start" />
        Back to monitor
      </Link>
      <header>
        <h1 className="text-[2.25rem] font-semibold tracking-[-0.045em] sm:text-[2.6rem]">Edit monitor</h1>
        <p className="mt-1 text-muted-foreground">Update the endpoint and its expected response behavior.</p>
      </header>
      <MonitorForm monitor={state.monitor} successHref={detailsHref} />
    </main>
  )
}
