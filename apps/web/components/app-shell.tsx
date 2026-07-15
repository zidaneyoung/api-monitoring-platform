"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  BellIcon,
  ChevronDownIcon,
  CircleHelpIcon,
  LayoutDashboardIcon,
  MailIcon,
  MessageCircleIcon,
  MonitorIcon,
  SettingsIcon,
} from "lucide-react"

import { ThemeToggle } from "@/components/theme-toggle"
import { Button, buttonVariants } from "@/components/ui/button"
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

function ApplicationHeader({ pathname }: { pathname: string }) {
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
        <Link
          href="/login"
          className={cn(buttonVariants({ variant: "ghost", size: "lg" }), "h-12 gap-3 px-1.5 sm:px-2")}
          aria-label="Open account page for Zidane Young"
        >
          <span className="grid size-11 place-items-center rounded-full bg-primary/10 text-sm font-semibold text-primary">ZY</span>
          <span className="hidden text-base font-medium md:block">Zidane Young</span>
          <ChevronDownIcon className="hidden size-4 text-muted-foreground md:block" aria-hidden="true" />
        </Link>
      </div>
    </header>
  )
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isStandalonePage = pathname === "/login" || pathname === "/register"

  if (isStandalonePage) return children

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
        <ApplicationHeader pathname={pathname} />
        {children}
      </div>
    </div>
  )
}
