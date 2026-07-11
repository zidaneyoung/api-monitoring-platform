import { AlertTriangleIcon } from "lucide-react"
import { useId, type ReactNode } from "react"

import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

type ErrorStateProps = {
  title: string
  description: string
  action?: ReactNode
  className?: string
}

export function ErrorState({ title, description, action, className }: ErrorStateProps) {
  const titleId = useId()
  const descriptionId = useId()

  return (
    <Card
      className={cn("items-center border-destructive/40 bg-destructive/5 py-12 text-center", className)}
      role="alert"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
    >
      <CardContent className="flex max-w-md flex-col items-center gap-3">
        <div className="rounded-full bg-destructive/10 p-3 text-destructive" aria-hidden="true">
          <AlertTriangleIcon className="size-7" />
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
