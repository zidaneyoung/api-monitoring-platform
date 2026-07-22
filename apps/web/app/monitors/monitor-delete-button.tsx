"use client"

import { Loader2Icon, Trash2Icon } from "lucide-react"
import { useEffect, useRef, useState } from "react"

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
import { deleteMonitor, type MonitorDto } from "@/lib/monitor-api"
import type { MonitorMutationAction } from "./monitor-pause-button"


function failureMessage(type: string): string {
  if (type === "unauthenticated") return "Your session has expired. Sign in and try again."
  if (type === "forbidden") return "You do not have permission to delete this monitor."
  if (type === "not_found") return "This monitor no longer exists or is not available to your account."
  if (type === "conflict") return "The monitor changed before it could be deleted. Review it and try again."
  if (type === "rate_limited") return "Too many requests were submitted. Wait a moment, then delete again."
  if (type === "timeout") return "The delete request timed out. Try again."
  if (type === "network_error") return "Unable to reach the service. Check your connection and try again."
  return "The monitor could not be deleted. Try again."
}

export function MonitorDeleteButton({
  monitor,
  onDeleted,
  className,
  pendingAction,
  onPendingActionChange,
}: {
  monitor: MonitorDto
  onDeleted: (monitorId: string) => void
  className?: string
  pendingAction?: MonitorMutationAction | null
  onPendingActionChange?: (action: MonitorMutationAction | null) => void
}) {
  const [open, setOpen] = useState(false)
  const [localPendingAction, setLocalPendingAction] = useState<MonitorMutationAction | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const requestPendingRef = useRef(false)
  const mountedRef = useRef(true)
  const completionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const activePendingAction = pendingAction === undefined ? localPendingAction : pendingAction
  const setPendingAction = onPendingActionChange ?? setLocalPendingAction
  const isSubmitting = activePendingAction === "delete"
  const hasPendingMutation = activePendingAction !== null

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (completionTimerRef.current) clearTimeout(completionTimerRef.current)
    }
  }, [])

  function handleOpenChange(nextOpen: boolean) {
    if (isSubmitting) return
    setOpen(nextOpen)
    if (nextOpen) {
      setError(null)
      setSuccess(null)
    }
  }

  async function remove() {
    if (requestPendingRef.current || activePendingAction !== null) return
    requestPendingRef.current = true
    setError(null)
    setPendingAction("delete")

    const outcome = await deleteMonitor(monitor.id)
    if (!mountedRef.current) return
    if (outcome.type === "success") {
      setSuccess(`${monitor.name} deleted.`)
      setOpen(false)
      completionTimerRef.current = setTimeout(() => {
        setPendingAction(null)
        requestPendingRef.current = false
        onDeleted(monitor.id)
      }, 500)
      return
    }

    setError(failureMessage(outcome.type))
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
              variant="destructive"
              size="lg"
              type="button"
              disabled={hasPendingMutation}
            />
          }
        >
          <Trash2Icon data-icon="inline-start" />
          Delete monitor
        </DialogTrigger>
        <DialogContent showCloseButton={!isSubmitting}>
          <DialogHeader>
            <DialogTitle className="text-destructive">Permanently delete {monitor.name}?</DialogTitle>
            <DialogDescription>
              This cannot be undone. The monitor and its related checks and incident history will be deleted.
            </DialogDescription>
          </DialogHeader>
          {error ? <p className="text-sm text-destructive" role="alert" aria-live="assertive">{error}</p> : null}
          <DialogFooter>
            <DialogClose render={<Button variant="outline" type="button" disabled={isSubmitting} />}>
              Cancel
            </DialogClose>
            <Button variant="destructive" type="button" disabled={isSubmitting} onClick={remove}>
              {isSubmitting ? <Loader2Icon className="animate-spin" data-icon="inline-start" /> : <Trash2Icon data-icon="inline-start" />}
              {isSubmitting ? "Deleting…" : "Delete permanently"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {success ? <p className="text-xs text-muted-foreground" role="status" aria-live="polite">{success}</p> : null}
    </div>
  )
}
