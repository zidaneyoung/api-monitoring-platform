export type MonitorTimestamp =
  | { kind: "missing"; display: string; original: null }
  | { kind: "invalid"; display: string; original: string }
  | { kind: "valid"; display: string; original: string }

const explicitTimeZone = /(?:Z|[+-]\d{2}:\d{2})$/i

export function parseApiTimestamp(value: string): number | null {
  if (!explicitTimeZone.test(value)) return null
  const timestamp = Date.parse(value)
  return Number.isFinite(timestamp) ? timestamp : null
}

export function formatMonitorTimestamp(
  value: string | null,
  options: { locale?: string | string[]; timeZone?: string } = {},
): MonitorTimestamp {
  if (value === null) return { kind: "missing", display: "—", original: null }

  const timestamp = parseApiTimestamp(value)
  if (timestamp === null) {
    return { kind: "invalid", display: "Unavailable", original: value }
  }

  try {
    const formatter = new Intl.DateTimeFormat(options.locale, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: options.timeZone,
    })
    return { kind: "valid", display: formatter.format(timestamp), original: value }
  } catch {
    return { kind: "invalid", display: "Unavailable", original: value }
  }
}
