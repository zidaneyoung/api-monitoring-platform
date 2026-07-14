"use client"

import { MoonIcon, SunIcon } from "lucide-react"

import { cn } from "@/lib/utils"

export function ThemeToggle({ className }: { className?: string }) {
  function toggleTheme() {
    const nextIsDark = document.documentElement.classList.toggle("dark")
    localStorage.setItem("theme", nextIsDark ? "dark" : "light")
  }

  return (
    <button
      className={cn(
        "theme-toggle grid size-9 place-items-center rounded-lg border border-border bg-background text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
        className
      )}
      type="button"
      onClick={toggleTheme}
      aria-label="Toggle color theme"
      title="Toggle color theme"
    >
      <SunIcon aria-hidden="true" className="size-5 dark:hidden" />
      <MoonIcon aria-hidden="true" className="hidden size-5 dark:block" />
    </button>
  )
}
