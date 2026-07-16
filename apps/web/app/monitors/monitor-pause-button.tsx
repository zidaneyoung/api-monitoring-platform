"use client"

import { Loader2Icon, PauseIcon, PlayIcon } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { pauseMonitor, type MonitorDto } from "@/lib/monitor-api"


function failureMessage(type: string): string {
  if (type === "unauthenticated") return "Your session has expired. Sign in and try again."
  if (type === "not_found") return "This monitor no longer exists or is not available to your account."
  if (type === "timeout") return "The pause request timed out. Try again."
  if (type === "network_error") return "Unable to reach the service. Check your connection and try again."
  return "The monitor could not be paused. Try again."
}

export function MonitorPauseButton({
  monitor,
  onPaused,
  className,
}: {
  monitor: MonitorDto
  onPaused: (monitor: MonitorDto) => void
  className?: string
}) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isPaused = monitor.status === "paused"

  async function pause() {
    if (isSubmitting || isPaused) return
    if (!window.confirm(`Pause ${monitor.name}? Future checks will stop until you resume it.`)) return

    setError(null)
    setIsSubmitting(true)
    const outcome = await pauseMonitor(monitor.id)
    setIsSubmitting(false)
    if (outcome.type === "success") {
      onPaused(outcome.data)
      return
    }
    setError(failureMessage(outcome.type))
  }

  return (
    <div className="grid gap-1.5">
      <Button className={className} variant="outline" size="lg" type="button" disabled={isPaused || isSubmitting} onClick={pause}>
        {isSubmitting ? <Loader2Icon className="animate-spin" data-icon="inline-start" /> : isPaused ? <PlayIcon data-icon="inline-start" /> : <PauseIcon data-icon="inline-start" />}
        {isSubmitting ? "Pausing…" : isPaused ? "Resume monitor" : "Pause monitor"}
      </Button>
      {error ? <p className="text-xs text-destructive" role="alert">{error}</p> : null}
    </div>
  )
}
