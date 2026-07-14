import { CircleHelpIcon, CircleIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

const statusDetails = {
  unknown: { label: "Unknown", icon: CircleHelpIcon, className: "border-status-unknown-foreground/15 bg-status-unknown text-status-unknown-foreground" },
  up: { label: "Up", icon: CircleIcon, className: "border-status-up-foreground/35 bg-status-up text-status-up-foreground" },
  down: { label: "Down", icon: CircleIcon, className: "border-status-down-foreground/35 bg-status-down text-status-down-foreground" },
  paused: { label: "Paused", icon: CircleIcon, className: "border-status-paused-foreground/35 bg-status-paused text-status-paused-foreground" },
} as const

export type MonitorStatus = keyof typeof statusDetails

export function StatusBadge({ status, className }: { status: MonitorStatus; className?: string }) {
  const details = statusDetails[status]
  const Icon = details.icon

  return (
    <Badge variant="outline" className={cn(details.className, className)}>
      <Icon aria-hidden="true" data-icon="inline-start" className={status === "unknown" ? undefined : "fill-current"} />
      {details.label}
    </Badge>
  )
}
