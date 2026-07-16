"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import {
  BellIcon,
  CircleHelpIcon,
  LayoutDashboardIcon,
  MailIcon,
  MessageCircleIcon,
  MonitorIcon,
  SettingsIcon,
} from "lucide-react"

import { ThemeToggle } from "@/components/theme-toggle"
import { LogoutButton } from "@/components/logout-button"
import { Button, buttonVariants } from "@/components/ui/button"
import { getCurrentUser, type CurrentUser } from "@/lib/auth-api"
import { authRouteWithNext, safeAuthRedirect } from "@/lib/auth-redirect"
import { cn } from "@/lib/utils"

const navigationItems = [
  { href: "/monitors", label: "Monitors", icon: MonitorIcon },
  { href: "/monitors/incidents", label: "Incidents", icon: BellIcon },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboardIcon },
  { label: "Alerts", icon: MailIcon },
  { label: "Settings", icon: SettingsIcon },
] as const

function isCurrentRoute(pathname: string, href: string) {
  if (href === "/monitors") {
    return pathname === href || (pathname.startsWith(`${href}/`) && !pathname.startsWith("/monitors/incidents"))
  }

  return pathname === href || pathname.startsWith(`${href}/`)
}

function Brand() {
  return (
    <Link className="inline-flex text-[1.7rem] font-bold leading-none tracking-[-0.055em] text-sidebar-foreground" href="/monitors">
      Uptime<span className="text-primary">Arc</span>
    </Link>
  )
}

function NavigationItem({
  item,
  pathname,
}: {
  item: (typeof navigationItems)[number]
  pathname: string
}) {
  const Icon = item.icon
  const href = "href" in item ? item.href : undefined
  const current = href ? isCurrentRoute(pathname, href) : false
  const className = cn(
    "flex h-[3.9rem] w-full shrink-0 items-center gap-4 rounded-xl px-5 text-base font-medium transition-colors focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50 lg:h-[3.45rem] lg:px-4 lg:text-[0.95rem] xl:h-[3.9rem] xl:px-5 xl:text-base",
    current
      ? "bg-sidebar-accent text-sidebar-accent-foreground"
      : "text-sidebar-foreground hover:bg-sidebar-accent/55"
  )

  if (href) {
    return (
      <Link href={href} aria-current={current ? "page" : undefined} className={className}>
        <Icon className="size-5 text-sidebar-muted xl:size-6" strokeWidth={1.7} aria-hidden="true" />
        {item.label}
      </Link>
    )
  }

  return (
    <button type="button" className={className}>
      <Icon className="size-5 text-sidebar-muted xl:size-6" strokeWidth={1.7} aria-hidden="true" />
      {item.label}
    </button>
  )
}

function ApplicationNavigation({ mobile = false }: { mobile?: boolean }) {
  const pathname = usePathname()

  return (
    <nav
      aria-label="Application navigation"
      className={cn(mobile ? "flex gap-1 overflow-x-auto pb-3" : "flex flex-col gap-1.5")}
    >
      {navigationItems.map((item) => (
        <NavigationItem key={item.label} item={item} pathname={pathname} />
      ))}
    </nav>
  )
}

function SupportNavigation() {
  return (
    <div className="flex flex-col gap-1.5 border-t border-sidebar-border pt-7">
      <button className="flex h-14 items-center gap-4 rounded-xl px-5 text-left text-base text-sidebar-foreground transition-colors hover:bg-sidebar-accent/55 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50" type="button">
        <CircleHelpIcon className="size-6 text-sidebar-muted" strokeWidth={1.7} aria-hidden="true" />
        Help &amp; docs
      </button>
      <button className="flex h-14 items-center gap-4 rounded-xl px-5 text-left text-base text-sidebar-foreground transition-colors hover:bg-sidebar-accent/55 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50" type="button">
        <MessageCircleIcon className="size-6 text-sidebar-muted" strokeWidth={1.7} aria-hidden="true" />
        Give feedback
      </button>
    </div>
  )
}

function initialsFromEmail(email: string): string {
  const localPart = email.split("@", 1)[0] ?? ""
  const segments = localPart.split(/[._-]+/).filter(Boolean)
  const initials = segments.length > 1
    ? segments.slice(0, 2).map((segment) => segment[0]).join("")
    : localPart.replace(/[^a-z0-9]/gi, "").slice(0, 2)

  return (initials || "U").toUpperCase()
}

function ApplicationHeader({
  pathname,
  user,
}: {
  pathname: string
  user?: CurrentUser
}) {
  const isMonitorList = pathname === "/monitors"
  const isIncidentHistory = pathname === "/monitors/incidents"

  return (
    <header className={cn(
      "sticky top-0 z-20 flex items-center border-b bg-background/95 px-4 backdrop-blur sm:px-6 lg:px-8 xl:px-11",
      isMonitorList ? "h-[6.4rem]" : isIncidentHistory ? "h-14" : "h-[4.25rem]"
    )}>
      <div className="ml-auto flex items-center gap-1.5 sm:gap-3">
        <ThemeToggle className="size-11 border-transparent bg-transparent text-foreground hover:bg-muted" />
        <Button className="relative size-11" variant="ghost" size="icon-lg" type="button" aria-label="Notifications" title="Notifications">
          <BellIcon className="size-6" strokeWidth={1.7} />
          <span className="absolute top-2.5 right-2.5 size-2.5 rounded-full border-2 border-background bg-primary" aria-hidden="true" />
        </Button>
        {user ? (
          <div className="flex min-w-0 items-center gap-2.5" aria-label={`Signed in as ${user.email}`}>
            <span className="grid size-10 shrink-0 place-items-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
              {initialsFromEmail(user.email)}
            </span>
            <span className="hidden max-w-40 truncate text-sm font-medium md:block xl:max-w-64" title={user.email}>
              {user.email}
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-2.5" role="status" aria-label="Loading account">
            <span className="size-10 animate-pulse rounded-full bg-muted motion-reduce:animate-none" />
            <span className="hidden h-4 w-32 animate-pulse rounded bg-muted motion-reduce:animate-none md:block" />
          </div>
        )}
        <LogoutButton className={cn(buttonVariants({ variant: "ghost", size: "lg" }), "h-11 px-2.5 sm:px-3")} />
      </div>
    </header>
  )
}

function ApplicationFrame({
  children,
  pathname,
  user,
}: {
  children: React.ReactNode
  pathname: string
  user?: CurrentUser
}) {
  return (
    <div className="min-h-svh bg-background lg:grid lg:grid-cols-[14.75rem_minmax(0,1fr)] xl:grid-cols-[17.25rem_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-svh flex-col border-r border-sidebar-border bg-sidebar px-3.5 py-8 text-sidebar-foreground lg:flex xl:px-5 xl:py-11">
        <div className="px-4"><Brand /></div>
        <div className="mt-9 xl:mt-12"><ApplicationNavigation /></div>
        <div className="mt-8 xl:mt-12"><SupportNavigation /></div>
      </aside>

      <div className="min-w-0">
        <div className="border-b border-sidebar-border bg-sidebar px-4 pt-4 text-sidebar-foreground lg:hidden">
          <div className="mb-4"><Brand /></div>
          <ApplicationNavigation mobile />
        </div>
        <ApplicationHeader pathname={pathname} user={user} />
        {children}
      </div>
    </div>
  )
}

function AuthenticatedShell({
  children,
  pathname,
}: {
  children: React.ReactNode
  pathname: string
}) {
  const router = useRouter()
  const [intendedDestination] = useState(pathname)
  const [user, setUser] = useState<CurrentUser | null>(null)

  useEffect(() => {
    let active = true

    void getCurrentUser().then((outcome) => {
      if (!active) return

      if (outcome.type === "success") {
        setUser(outcome.data)
        return
      }

      if (outcome.type === "unauthenticated") {
        router.replace(authRouteWithNext("/login", intendedDestination))
        return
      }

      const destination = safeAuthRedirect(intendedDestination)
      router.replace(`/auth-unavailable?next=${encodeURIComponent(destination)}`)
    })

    return () => {
      active = false
    }
  }, [intendedDestination, router])

  return (
    <ApplicationFrame pathname={pathname} user={user ?? undefined}>
      {user ? children : (
        <section className="grid min-h-[45vh] place-items-center px-6" aria-live="polite" aria-busy="true">
          <div className="w-full max-w-md space-y-4" role="status">
            <span className="sr-only">Checking your session…</span>
            <div className="h-7 w-44 animate-pulse rounded bg-muted motion-reduce:animate-none" />
            <div className="h-28 animate-pulse rounded-xl bg-muted/70 motion-reduce:animate-none" />
          </div>
        </section>
      )}
    </ApplicationFrame>
  )
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isStandalonePage = (
    pathname === "/login"
    || pathname === "/register"
    || pathname === "/auth-unavailable"
  )

  if (isStandalonePage) return children

  return <AuthenticatedShell pathname={pathname}>{children}</AuthenticatedShell>
}
