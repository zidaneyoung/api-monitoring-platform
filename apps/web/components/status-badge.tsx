import { CircleHelpIcon, CirclePauseIcon, CircleXIcon, CircleCheckIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

const statusDetails = {
  unknown: { label: "Unknown", icon: CircleHelpIcon, className: "bg-status-unknown text-status-unknown-foreground" },
  up: { label: "Up", icon: CircleCheckIcon, className: "bg-status-up text-status-up-foreground" },
  down: { label: "Down", icon: CircleXIcon, className: "bg-status-down text-status-down-foreground" },
  paused: { label: "Paused", icon: CirclePauseIcon, className: "bg-status-paused text-status-paused-foreground" },
} as const

export type MonitorStatus = keyof typeof statusDetails

export function StatusBadge({ status, className }: { status: MonitorStatus; className?: string }) {
  const details = statusDetails[status]
  const Icon = details.icon

  return (
    <Badge className={cn(details.className, className)}>
      <Icon aria-hidden="true" data-icon="inline-start" strokeWidth={3} />
      {details.label}
    </Badge>
  )
}
