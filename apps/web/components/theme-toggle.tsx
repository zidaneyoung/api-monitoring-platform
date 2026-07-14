"use client"

import { MoonIcon, SunIcon } from "lucide-react"

import { Button } from "@/components/ui/button"

export function ThemeToggle({ className }: { className?: string }) {
  function toggleTheme() {
    const isDark = document.documentElement.classList.toggle("dark")
    localStorage.setItem("theme", isDark ? "dark" : "light")
  }

  return (
    <Button className={className} variant="outline" size="icon" onClick={toggleTheme} aria-label="Toggle color theme">
      <SunIcon aria-hidden="true" className="dark:hidden" />
      <MoonIcon aria-hidden="true" className="hidden dark:block" />
    </Button>
  )
}
