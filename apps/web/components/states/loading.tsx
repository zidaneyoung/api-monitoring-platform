import { Loader2Icon } from "lucide-react"

import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { cn } from "@/lib/utils"

type LoadingStateProps = {
  label?: string
  count?: number
  className?: string
}

export function LoadingState({
  label = "Loading content",
  count = 2,
  className,
}: LoadingStateProps) {
  return (
    <div
      className={cn("grid gap-4 lg:grid-cols-2", className)}
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <span className="sr-only">{label}</span>
      {Array.from({ length: count }, (_, index) => (
        <Card key={index} aria-hidden="true" className="relative overflow-hidden">
          <CardHeader>
            <div className="h-5 w-2/5 animate-pulse rounded-md bg-muted" />
            <div className="h-4 w-3/5 animate-pulse rounded-md bg-muted/70" />
          </CardHeader>
          <CardContent className="grid gap-3">
            <div className="h-20 animate-pulse rounded-lg bg-muted" />
            <div className="h-10 animate-pulse rounded-lg bg-muted/70" />
          </CardContent>
          <Loader2Icon className="absolute right-4 top-4 size-4 animate-spin text-muted-foreground" />
        </Card>
      ))}
    </div>
  )
}
