import type { MonitorStatus } from "@/components/status-badge"

export type Monitor = {
  id: string
  name: string
  url: string
  status: MonitorStatus
  lastCheck: string
  lastCheckTime: string
  responseTime: string
}

export const mockMonitors: Monitor[] = [
  {
    id: "public-api",
    name: "Public API",
    url: "https://api.example.com/health",
    status: "up",
    lastCheck: "2 minutes ago",
    lastCheckTime: "2:15 PM",
    responseTime: "184 ms",
  },
  {
    id: "checkout",
    name: "Checkout",
    url: "https://example.com/checkout",
    status: "down",
    lastCheck: "1 minute ago",
    lastCheckTime: "2:16 PM",
    responseTime: "1,204 ms",
  },
  {
    id: "staging",
    name: "Staging",
    url: "https://staging.example.com",
    status: "paused",
    lastCheck: "Paused 3 days ago",
    lastCheckTime: "May 30, 2:15 PM",
    responseTime: "-",
  },
]

export function getMonitorById(monitorId: string) {
  return mockMonitors.find((monitor) => monitor.id === monitorId)
}
