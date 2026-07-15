"use client"

import { useState, type ReactNode } from "react"
import { useRouter } from "next/navigation"

import { logoutUser } from "@/lib/auth-api"


export function LogoutButton({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  const router = useRouter()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState("")

  async function handleLogout() {
    setIsSubmitting(true)
    setError("")

    try {
      await logoutUser()
      router.replace("/login")
      router.refresh()
    } catch (logoutError) {
      setError(logoutError instanceof Error ? logoutError.message : "Unable to log out. Try again.")
      setIsSubmitting(false)
    }
  }

  return (
    <button
      type="button"
      className={className}
      aria-label="Log out"
      aria-busy={isSubmitting}
      disabled={isSubmitting}
      onClick={handleLogout}
    >
      {children}
      <span className="sr-only" role="status" aria-live="polite">{error}</span>
    </button>
  )
}
