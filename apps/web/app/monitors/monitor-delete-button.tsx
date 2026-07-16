"use client"

import { Loader2Icon, Trash2Icon } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { deleteMonitor, type MonitorDto } from "@/lib/monitor-api"


function failureMessage(type: string): string {
  if (type === "unauthenticated") return "Your session has expired. Sign in and try again."
  if (type === "not_found") return "This monitor no longer exists or is not available to your account."
  if (type === "timeout") return "The delete request timed out. Try again."
  if (type === "network_error") return "Unable to reach the service. Check your connection and try again."
  return "The monitor could not be deleted. Try again."
}

export function MonitorDeleteButton({
  monitor,
  onDeleted,
  className,
}: {
  monitor: MonitorDto
  onDeleted: (monitorId: string) => void
  className?: string
}) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function remove() {
    if (isSubmitting) return
    const confirmed = window.confirm(
      `Permanently delete ${monitor.name}? Its checks and incident history will also be deleted. This cannot be undone.`,
    )
    if (!confirmed) return

    setError(null)
    setIsSubmitting(true)
    const outcome = await deleteMonitor(monitor.id)
    setIsSubmitting(false)
    if (outcome.type === "success") {
      onDeleted(monitor.id)
      return
    }
    setError(failureMessage(outcome.type))
  }

  return (
    <div className="grid gap-1.5">
      <Button className={className} variant="destructive" size="lg" type="button" disabled={isSubmitting} onClick={remove}>
        {isSubmitting ? <Loader2Icon className="animate-spin" data-icon="inline-start" /> : <Trash2Icon data-icon="inline-start" />}
        {isSubmitting ? "Deleting…" : "Delete monitor"}
      </Button>
      {error ? <p className="text-xs text-destructive" role="alert">{error}</p> : null}
    </div>
  )
}
