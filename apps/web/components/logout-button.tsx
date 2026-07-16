"use client"

import { LoaderCircleIcon, LogOutIcon } from "lucide-react"
import { useRouter } from "next/navigation"
import { useState } from "react"

import { logoutUser } from "@/lib/auth-api"
import { cn } from "@/lib/utils"


export function LogoutButton({
  className,
}: {
  className?: string
}) {
  const router = useRouter()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState("")

  async function handleLogout() {
    setIsSubmitting(true)
    setError("")

    const outcome = await logoutUser()
    if (
      outcome.type === "success"
      || outcome.type === "cleared"
      || outcome.type === "unauthenticated"
    ) {
      router.replace("/login")
      router.refresh()
      return
    }

    setError(
      outcome.type === "timeout"
        ? "Logout timed out. Your session may still be active. Try again."
        : outcome.type === "network_error"
          ? "Unable to reach the service. Your session may still be active. Try again."
          : "Unable to log out. Your session may still be active. Try again.",
    )
    setIsSubmitting(false)
  }

  return (
    <div className="relative">
      <button
        type="button"
        className={cn("gap-2", className)}
        aria-label={isSubmitting ? "Logging out" : "Log out"}
        aria-busy={isSubmitting}
        disabled={isSubmitting}
        title={isSubmitting ? "Logging out" : "Log out"}
        onClick={handleLogout}
      >
        {isSubmitting ? (
          <LoaderCircleIcon className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
        ) : (
          <LogOutIcon className="size-4" aria-hidden="true" />
        )}
        <span className="hidden sm:inline">{isSubmitting ? "Logging out…" : "Log out"}</span>
      </button>
      {error ? (
        <p
          className="absolute top-[calc(100%+0.5rem)] right-0 z-30 w-72 rounded-lg border border-destructive/25 bg-popover px-3 py-2 text-sm text-destructive shadow-lg"
          role="alert"
        >
          {error}
        </p>
      ) : null}
    </div>
  )
}
