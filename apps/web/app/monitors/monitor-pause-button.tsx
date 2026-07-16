"use client"

import { Loader2Icon, PauseIcon, PlayIcon } from "lucide-react"
import { useRef, useState } from "react"

import { Button } from "@/components/ui/button"
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
import { pauseMonitor, resumeMonitor, type MonitorDto } from "@/lib/monitor-api"


export type MonitorMutationAction = "pause" | "resume" | "delete"

function failureMessage(type: string, action: "pause" | "resume"): string {
  if (type === "unauthenticated") return "Your session has expired. Sign in and try again."
  if (type === "forbidden") return `You do not have permission to ${action} this monitor.`
  if (type === "not_found") return "This monitor no longer exists or is not available to your account."
  if (type === "conflict") return `The monitor changed before it could be ${action}d. Review it and try again.`
  if (type === "rate_limited") return `Too many requests were submitted. Wait a moment, then ${action} again.`
  if (type === "timeout") return `The ${action} request timed out. Try again.`
  if (type === "network_error") return "Unable to reach the service. Check your connection and try again."
  return `The monitor could not be ${action}d. Try again.`
}

export function MonitorStateButton({
  monitor,
  onChanged,
  className,
  pendingAction,
  onPendingActionChange,
}: {
  monitor: MonitorDto
  onChanged: (monitor: MonitorDto) => void
  className?: string
  pendingAction?: MonitorMutationAction | null
  onPendingActionChange?: (action: MonitorMutationAction | null) => void
}) {
  const [open, setOpen] = useState(false)
  const [localPendingAction, setLocalPendingAction] = useState<MonitorMutationAction | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const requestPendingRef = useRef(false)
  const activePendingAction = pendingAction === undefined ? localPendingAction : pendingAction
  const setPendingAction = onPendingActionChange ?? setLocalPendingAction
  const isPaused = monitor.status === "paused"
  const action = isPaused ? "resume" : "pause"
  const isSubmitting = activePendingAction === action
  const hasPendingMutation = activePendingAction !== null

  function handleOpenChange(nextOpen: boolean) {
    if (isSubmitting) return
    setOpen(nextOpen)
    if (nextOpen) {
      setError(null)
      setSuccess(null)
    }
  }

  async function changeState() {
    if (requestPendingRef.current || activePendingAction !== null) return
    requestPendingRef.current = true
    setError(null)
    setPendingAction(action)

    const outcome = action === "resume"
      ? await resumeMonitor(monitor.id)
      : await pauseMonitor(monitor.id)

    if (outcome.type === "success") {
      const message = `${monitor.name} ${action === "resume" ? "resumed" : "paused"}.`
      setSuccess(message)
      setOpen(false)
      setPendingAction(null)
      requestPendingRef.current = false
      onChanged(outcome.data)
      return
    }

    setError(failureMessage(outcome.type, action))
    setPendingAction(null)
    requestPendingRef.current = false
  }

  return (
    <div className="grid gap-1.5">
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogTrigger
          render={
            <Button
              className={className}
              variant="outline"
              size="lg"
              type="button"
              disabled={hasPendingMutation}
            />
          }
        >
          {isPaused ? <PlayIcon data-icon="inline-start" /> : <PauseIcon data-icon="inline-start" />}
          {isPaused ? "Resume monitor" : "Pause monitor"}
        </DialogTrigger>
        <DialogContent showCloseButton={!isSubmitting}>
          <DialogHeader>
            <DialogTitle>{isPaused ? "Resume" : "Pause"} {monitor.name}?</DialogTitle>
            <DialogDescription>
              {isPaused
                ? "Future checks may continue using the monitor’s current schedule."
                : "Future checks will stop until you resume this monitor."}
            </DialogDescription>
          </DialogHeader>
          {error ? <p className="text-sm text-destructive" role="alert" aria-live="assertive">{error}</p> : null}
          <DialogFooter>
            <DialogClose render={<Button variant="outline" type="button" disabled={isSubmitting} />}>
              Cancel
            </DialogClose>
            <Button type="button" disabled={isSubmitting} onClick={changeState}>
              {isSubmitting ? <Loader2Icon className="animate-spin" data-icon="inline-start" /> : null}
              {isSubmitting
                ? `${isPaused ? "Resuming" : "Pausing"}…`
                : isPaused ? "Resume monitor" : "Pause monitor"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {success ? <p className="text-xs text-muted-foreground" role="status" aria-live="polite">{success}</p> : null}
    </div>
  )
}
