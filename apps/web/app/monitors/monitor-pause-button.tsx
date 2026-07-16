"use client"

import { Loader2Icon, PauseIcon, PlayIcon } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { pauseMonitor, resumeMonitor, type MonitorDto } from "@/lib/monitor-api"


function failureMessage(type: string, action: "pause" | "resume"): string {
  if (type === "unauthenticated") return "Your session has expired. Sign in and try again."
  if (type === "not_found") return "This monitor no longer exists or is not available to your account."
  if (type === "timeout") return `The ${action} request timed out. Try again.`
  if (type === "network_error") return "Unable to reach the service. Check your connection and try again."
  return `The monitor could not be ${action}d. Try again.`
}

export function MonitorStateButton({
  monitor,
  onChanged,
  className,
}: {
  monitor: MonitorDto
  onChanged: (monitor: MonitorDto) => void
  className?: string
}) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isPaused = monitor.status === "paused"

  async function changeState() {
    if (isSubmitting) return
    const action = isPaused ? "resume" : "pause"
    if (action === "pause" && !window.confirm(`Pause ${monitor.name}? Future checks will stop until you resume it.`)) return

    setError(null)
    setIsSubmitting(true)
    const outcome = isPaused
      ? await resumeMonitor(monitor.id)
      : await pauseMonitor(monitor.id)
    setIsSubmitting(false)
    if (outcome.type === "success") {
      onChanged(outcome.data)
      return
    }
    setError(failureMessage(outcome.type, action))
  }

  return (
    <div className="grid gap-1.5">
      <Button className={className} variant="outline" size="lg" type="button" disabled={isSubmitting} onClick={changeState}>
        {isSubmitting ? <Loader2Icon className="animate-spin" data-icon="inline-start" /> : isPaused ? <PlayIcon data-icon="inline-start" /> : <PauseIcon data-icon="inline-start" />}
        {isSubmitting ? `${isPaused ? "Resuming" : "Pausing"}…` : isPaused ? "Resume monitor" : "Pause monitor"}
      </Button>
      {error ? <p className="text-xs text-destructive" role="alert">{error}</p> : null}
    </div>
  )
}
