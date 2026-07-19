const errorLabels: Record<string, string> = {
  unsafe_destination: "Unsafe destination",
  response_limit: "Response too large",
  redirect: "Redirect failed",
  connect_timeout: "Connection timeout",
  request_timeout: "Request timeout",
  dns: "DNS failure",
  connection_refused: "Connection refused",
  tls: "TLS failure",
  connection: "Connection failure",
  request: "Request failure",
  internal: "Monitoring error",
  unexpected_status: "Unexpected HTTP status",
  http_status: "Unexpected HTTP status",
}

export function formatMonitorResponseTime(value: number | null): string {
  return value === null ? "—" : `${value.toLocaleString()} ms`
}

export function formatMonitorStatusCode(value: number | null): string {
  return value === null ? "—" : String(value)
}

export function formatMonitorErrorCategory(value: string | null): string | null {
  if (value === null) return null
  return errorLabels[value] ?? "Monitoring error"
}
