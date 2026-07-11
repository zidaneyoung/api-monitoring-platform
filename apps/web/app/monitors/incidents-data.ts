export type IncidentSection = "open" | "resolved";

export type IncidentRecord = {
  id: string;
  section: IncidentSection;
  title: string;
  monitorName: string;
  status: string;
  openedAt: string;
  resolvedAt?: string;
  duration: string;
  summary: string;
};

export const mockIncidents: IncidentRecord[] = [
  {
    id: "inc-2048",
    section: "open",
    title: "Checkout API latency spike",
    monitorName: "Checkout API",
    status: "Investigating",
    openedAt: "2026-07-09T10:14:00Z",
    duration: "1h 24m and counting",
    summary: "Latency breach on the checkout endpoint. Error rate remains elevated.",
  },
  {
    id: "inc-2047",
    section: "open",
    title: "Billing webhook timeout",
    monitorName: "Billing Webhook",
    status: "Triggered",
    openedAt: "2026-07-09T09:02:00Z",
    duration: "2h 36m and counting",
    summary: "Upstream webhook retries still timing out after repeated attempts.",
  },
  {
    id: "inc-2046",
    section: "open",
    title: "Auth service 5xx burst",
    monitorName: "Auth Service",
    status: "Mitigating",
    openedAt: "2026-07-09T08:31:00Z",
    duration: "3h 07m and counting",
    summary: "Brief 5xx burst on auth service. Traffic stabilized but incident stays open.",
  },
  {
    id: "inc-2039",
    section: "resolved",
    title: "Search API slow responses",
    monitorName: "Search API",
    status: "Resolved",
    openedAt: "2026-07-08T16:20:00Z",
    resolvedAt: "2026-07-08T17:05:00Z",
    duration: "45m",
    summary: "Search latency recovered after cache warm-up and node restart.",
  },
  {
    id: "inc-2038",
    section: "resolved",
    title: "Payments endpoint outage",
    monitorName: "Payments API",
    status: "Resolved",
    openedAt: "2026-07-08T12:43:00Z",
    resolvedAt: "2026-07-08T13:58:00Z",
    duration: "1h 15m",
    summary: "Short outage caused by a bad deploy. Traffic restored after rollback.",
  },
  {
    id: "inc-2037",
    section: "resolved",
    title: "Notification queue lag",
    monitorName: "Notifications Worker",
    status: "Resolved",
    openedAt: "2026-07-07T21:12:00Z",
    resolvedAt: "2026-07-07T21:34:00Z",
    duration: "22m",
    summary: "Queue lag cleared after autoscaling worker pool and draining backlog.",
  },
];

export function getIncidents(section: IncidentSection) {
  return mockIncidents.filter((incident) => incident.section === section);
}

export function getIncidentById(incidentId: string) {
  return mockIncidents.find((incident) => incident.id === incidentId);
}
