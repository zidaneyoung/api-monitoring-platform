import { InboxIcon } from "lucide-react"
import { useId, type ReactNode } from "react"

import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

type EmptyStateProps = {
  title: string
  description: string
  action?: ReactNode
  icon?: ReactNode
  className?: string
}

export function EmptyState({ title, description, action, icon, className }: EmptyStateProps) {
  const titleId = useId()
  const descriptionId = useId()

  return (
    <Card
      className={cn("items-center border-dashed py-12 text-center", className)}
      role="status"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
    >
      <CardContent className="flex max-w-md flex-col items-center gap-3">
        <div className="rounded-full bg-muted p-3 text-muted-foreground" aria-hidden="true">
          {icon ?? <InboxIcon className="size-7" />}
        </div>
        <div>
          <h2 id={titleId}>{title}</h2>
          <p id={descriptionId} className="mt-1 text-muted-foreground">{description}</p>
        </div>
        {action}
      </CardContent>
    </Card>
  )
}
