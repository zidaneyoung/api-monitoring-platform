"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { ThemeToggle } from "@/components/theme-toggle"
import { buttonVariants } from "@/components/ui/button"

const navigationItems = [
  { href: "/", label: "Home" },
  { href: "/monitors", label: "Monitors" },
  { href: "/monitors/incidents", label: "Incidents" },
  { href: "/dev/components", label: "Components" },
  { href: "/login", label: "Log in" },
] as const

function isCurrentRoute(pathname: string, href: string) {
  if (href === "/") {
    return pathname === href
  }

  if (href === "/monitors") {
    return pathname === href || (pathname.startsWith(`${href}/`) && !pathname.startsWith("/monitors/incidents"))
  }

  return pathname === href || pathname.startsWith(`${href}/`)
}

export function AppNavigation() {
  const pathname = usePathname()
  const isAuthenticationPage = pathname === "/login" || pathname === "/register"

  if (isAuthenticationPage || pathname === "/dashboard") {
    return null
  }

  return (
    <header className="border-b bg-background">
      <nav
        className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8"
        aria-label="Primary navigation"
      >
        <Link className="font-semibold tracking-tight" href="/">
          API Monitoring Platform
        </Link>
        <div className="flex flex-wrap items-center justify-end gap-1">
          {navigationItems.map((item) => {
            const current = isCurrentRoute(pathname, item.href)

            return (
              <Link
                key={item.href}
                className={buttonVariants({ variant: current ? "secondary" : "ghost", size: "sm" })}
                href={item.href}
                aria-current={current ? "page" : undefined}
              >
                {item.label}
              </Link>
            )
          })}
          <ThemeToggle />
        </div>
      </nav>
    </header>
  )
}
