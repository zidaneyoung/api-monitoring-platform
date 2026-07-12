"use client"

import { MoonIcon, SunIcon } from "lucide-react"

export function ThemeToggle() {
  function toggleTheme() {
    const nextIsDark = document.documentElement.classList.toggle("dark")
    localStorage.setItem("theme", nextIsDark ? "dark" : "light")
  }

  return (
    <button
      className="theme-toggle"
      type="button"
      onClick={toggleTheme}
      aria-label="Toggle color theme"
      title="Toggle color theme"
    >
      <SunIcon aria-hidden="true" className="dark:hidden" />
      <MoonIcon aria-hidden="true" className="hidden dark:block" />
    </button>
  )
}
