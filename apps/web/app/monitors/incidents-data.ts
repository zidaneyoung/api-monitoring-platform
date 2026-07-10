export type IncidentSection = "open" | "resolved";

export type IncidentFailure = {
  checkId: string;
  observedAt: string;
  location: string;
  statusCode?: number;
  responseTime: string;
  message: string;
  bodyPreview: string;
};

export type IncidentCheckStatus = "failed" | "degraded" | "recovered";

export type IncidentCheck = {
  id: string;
  checkedAt: string;
  status: IncidentCheckStatus;
  location: string;
  statusCode?: number;
  responseTime: string;
  failure: string;
};

export type IncidentTimelineEvent = {
  id: string;
  occurredAt: string;
  title: string;
  description: string;
};

export type IncidentRecord = {
  id: string;
  section: IncidentSection;
  title: string;
  monitorId: string;
  monitorName: string;
  status: string;
  openedAt: string;
  resolvedAt?: string;
  duration: string;
  summary: string;
  triggeringFailure: IncidentFailure;
  relatedChecks: IncidentCheck[];
  timeline: IncidentTimelineEvent[];
};

export const mockIncidents: IncidentRecord[] = [
  {
    id: "inc-2048",
    section: "open",
    title: "Checkout API latency spike",
    monitorId: "checkout",
    monitorName: "Checkout API",
    status: "Investigating",
    openedAt: "2026-07-09T10:14:00Z",
    duration: "1h 24m and counting",
    summary: "Latency breach on the checkout endpoint. Error rate remains elevated.",
    triggeringFailure: {
      checkId: "chk-9008",
      observedAt: "2026-07-09T10:14:00Z",
      location: "us-east-1",
      statusCode: 503,
      responseTime: "4,820 ms",
      message: "Checkout health check exceeded latency threshold.",
      bodyPreview: "<html>Service Unavailable</html>",
    },
    relatedChecks: [
      {
        id: "chk-9008",
        checkedAt: "2026-07-09T10:14:00Z",
        status: "failed",
        location: "us-east-1",
        statusCode: 503,
        responseTime: "4,820 ms",
        failure: "Latency threshold exceeded.",
      },
      {
        id: "chk-9009",
        checkedAt: "2026-07-09T10:19:00Z",
        status: "degraded",
        location: "eu-west-1",
        statusCode: 200,
        responseTime: "2,190 ms",
        failure: "Slow response remained above warning threshold.",
      },
      {
        id: "chk-9010",
        checkedAt: "2026-07-09T10:24:00Z",
        status: "failed",
        location: "us-west-2",
        statusCode: 502,
        responseTime: "5,004 ms",
        failure: "Gateway returned an upstream error.",
      },
    ],
    timeline: [
      {
        id: "evt-2048-1",
        occurredAt: "2026-07-09T10:14:00Z",
        title: "Incident opened",
        description: "Checkout API failed from us-east-1 and opened an incident.",
      },
      {
        id: "evt-2048-2",
        occurredAt: "2026-07-09T10:19:00Z",
        title: "Latency confirmed",
        description: "Second check remained above warning threshold.",
      },
      {
        id: "evt-2048-3",
        occurredAt: "2026-07-09T10:24:00Z",
        title: "Impact widened",
        description: "us-west-2 check reported a gateway failure.",
      },
    ],
  },
  {
    id: "inc-2047",
    section: "open",
    title: "Billing webhook timeout",
    monitorId: "public-api",
    monitorName: "Billing Webhook",
    status: "Triggered",
    openedAt: "2026-07-09T09:02:00Z",
    duration: "2h 36m and counting",
    summary: "Upstream webhook retries still timing out after repeated attempts.",
    triggeringFailure: {
      checkId: "chk-8997",
      observedAt: "2026-07-09T09:02:00Z",
      location: "us-west-2",
      responseTime: "30,000 ms",
      message: "Webhook check timed out before receiving a response.",
      bodyPreview: "Request timed out after 30 seconds.",
    },
    relatedChecks: [
      {
        id: "chk-8997",
        checkedAt: "2026-07-09T09:02:00Z",
        status: "failed",
        location: "us-west-2",
        responseTime: "30,000 ms",
        failure: "Request timeout.",
      },
      {
        id: "chk-8998",
        checkedAt: "2026-07-09T09:07:00Z",
        status: "failed",
        location: "us-east-1",
        responseTime: "30,000 ms",
        failure: "Retry timed out.",
      },
    ],
    timeline: [
      {
        id: "evt-2047-1",
        occurredAt: "2026-07-09T09:02:00Z",
        title: "Incident opened",
        description: "Billing webhook timed out from us-west-2.",
      },
      {
        id: "evt-2047-2",
        occurredAt: "2026-07-09T09:07:00Z",
        title: "Retry failed",
        description: "Follow-up check timed out from us-east-1.",
      },
    ],
  },
  {
    id: "inc-2046",
    section: "open",
    title: "Auth service 5xx burst",
    monitorId: "public-api",
    monitorName: "Auth Service",
    status: "Mitigating",
    openedAt: "2026-07-09T08:31:00Z",
    duration: "3h 07m and counting",
    summary: "Brief 5xx burst on auth service. Traffic stabilized but incident stays open.",
    triggeringFailure: {
      checkId: "chk-8984",
      observedAt: "2026-07-09T08:31:00Z",
      location: "eu-west-1",
      statusCode: 500,
      responseTime: "931 ms",
      message: "Auth service returned HTTP 500.",
      bodyPreview: "{\"error\":\"internal_server_error\"}",
    },
    relatedChecks: [
      {
        id: "chk-8984",
        checkedAt: "2026-07-09T08:31:00Z",
        status: "failed",
        location: "eu-west-1",
        statusCode: 500,
        responseTime: "931 ms",
        failure: "HTTP 500.",
      },
      {
        id: "chk-8985",
        checkedAt: "2026-07-09T08:36:00Z",
        status: "recovered",
        location: "us-east-1",
        statusCode: 200,
        responseTime: "182 ms",
        failure: "Recovered.",
      },
    ],
    timeline: [
      {
        id: "evt-2046-1",
        occurredAt: "2026-07-09T08:31:00Z",
        title: "Incident opened",
        description: "Auth endpoint returned HTTP 500 from eu-west-1.",
      },
      {
        id: "evt-2046-2",
        occurredAt: "2026-07-09T08:36:00Z",
        title: "Traffic stabilized",
        description: "Follow-up check returned HTTP 200.",
      },
    ],
  },
  {
    id: "inc-2039",
    section: "resolved",
    title: "Search API slow responses",
    monitorId: "public-api",
    monitorName: "Search API",
    status: "Resolved",
    openedAt: "2026-07-08T16:20:00Z",
    resolvedAt: "2026-07-08T17:05:00Z",
    duration: "45m",
    summary: "Search latency recovered after cache warm-up and node restart.",
    triggeringFailure: {
      checkId: "chk-8841",
      observedAt: "2026-07-08T16:20:00Z",
      location: "us-east-1",
      statusCode: 200,
      responseTime: "2,804 ms",
      message: "Search API response time exceeded critical threshold.",
      bodyPreview: "{\"took\":2804,\"timed_out\":false}",
    },
    relatedChecks: [
      {
        id: "chk-8841",
        checkedAt: "2026-07-08T16:20:00Z",
        status: "degraded",
        location: "us-east-1",
        statusCode: 200,
        responseTime: "2,804 ms",
        failure: "Critical latency threshold exceeded.",
      },
      {
        id: "chk-8849",
        checkedAt: "2026-07-08T17:05:00Z",
        status: "recovered",
        location: "us-east-1",
        statusCode: 200,
        responseTime: "205 ms",
        failure: "Recovered.",
      },
    ],
    timeline: [
      {
        id: "evt-2039-1",
        occurredAt: "2026-07-08T16:20:00Z",
        title: "Incident opened",
        description: "Search API exceeded the critical latency threshold.",
      },
      {
        id: "evt-2039-2",
        occurredAt: "2026-07-08T16:42:00Z",
        title: "Mitigation applied",
        description: "Cache warm-up started after node restart.",
      },
      {
        id: "evt-2039-3",
        occurredAt: "2026-07-08T17:05:00Z",
        title: "Incident resolved",
        description: "Search API returned to normal latency.",
      },
    ],
  },
  {
    id: "inc-2038",
    section: "resolved",
    title: "Payments endpoint outage",
    monitorId: "checkout",
    monitorName: "Payments API",
    status: "Resolved",
    openedAt: "2026-07-08T12:43:00Z",
    resolvedAt: "2026-07-08T13:58:00Z",
    duration: "1h 15m",
    summary: "Short outage caused by a bad deploy. Traffic restored after rollback.",
    triggeringFailure: {
      checkId: "chk-8812",
      observedAt: "2026-07-08T12:43:00Z",
      location: "us-west-2",
      statusCode: 503,
      responseTime: "1,120 ms",
      message: "Payments endpoint returned service unavailable.",
      bodyPreview: "upstream connect error or disconnect/reset before headers",
    },
    relatedChecks: [
      {
        id: "chk-8812",
        checkedAt: "2026-07-08T12:43:00Z",
        status: "failed",
        location: "us-west-2",
        statusCode: 503,
        responseTime: "1,120 ms",
        failure: "HTTP 503.",
      },
      {
        id: "chk-8827",
        checkedAt: "2026-07-08T13:58:00Z",
        status: "recovered",
        location: "us-west-2",
        statusCode: 200,
        responseTime: "194 ms",
        failure: "Recovered.",
      },
    ],
    timeline: [
      {
        id: "evt-2038-1",
        occurredAt: "2026-07-08T12:43:00Z",
        title: "Incident opened",
        description: "Payments endpoint returned HTTP 503.",
      },
      {
        id: "evt-2038-2",
        occurredAt: "2026-07-08T13:21:00Z",
        title: "Rollback started",
        description: "Bad deployment identified and rollback began.",
      },
      {
        id: "evt-2038-3",
        occurredAt: "2026-07-08T13:58:00Z",
        title: "Incident resolved",
        description: "Payments endpoint recovered after rollback.",
      },
    ],
  },
  {
    id: "inc-2037",
    section: "resolved",
    title: "Notification queue lag",
    monitorId: "staging",
    monitorName: "Notifications Worker",
    status: "Resolved",
    openedAt: "2026-07-07T21:12:00Z",
    resolvedAt: "2026-07-07T21:34:00Z",
    duration: "22m",
    summary: "Queue lag cleared after autoscaling worker pool and draining backlog.",
    triggeringFailure: {
      checkId: "chk-8754",
      observedAt: "2026-07-07T21:12:00Z",
      location: "us-east-1",
      responseTime: "8,400 ms",
      message: "Worker heartbeat lag exceeded threshold.",
      bodyPreview: "queue_lag_seconds=8400",
    },
    relatedChecks: [
      {
        id: "chk-8754",
        checkedAt: "2026-07-07T21:12:00Z",
        status: "degraded",
        location: "us-east-1",
        responseTime: "8,400 ms",
        failure: "Queue lag above threshold.",
      },
      {
        id: "chk-8759",
        checkedAt: "2026-07-07T21:34:00Z",
        status: "recovered",
        location: "us-east-1",
        responseTime: "620 ms",
        failure: "Recovered.",
      },
    ],
    timeline: [
      {
        id: "evt-2037-1",
        occurredAt: "2026-07-07T21:12:00Z",
        title: "Incident opened",
        description: "Worker heartbeat lag exceeded threshold.",
      },
      {
        id: "evt-2037-2",
        occurredAt: "2026-07-07T21:25:00Z",
        title: "Workers scaled",
        description: "Worker pool scaled up to drain backlog.",
      },
      {
        id: "evt-2037-3",
        occurredAt: "2026-07-07T21:34:00Z",
        title: "Incident resolved",
        description: "Queue lag returned below threshold.",
      },
    ],
  },
];

export function getIncidents(section: IncidentSection) {
  return mockIncidents.filter((incident) => incident.section === section);
}

export function getIncidentById(incidentId: string) {
  return mockIncidents.find((incident) => incident.id === incidentId);
}
