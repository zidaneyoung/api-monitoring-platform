export type MonitorTimestamp =
  | { kind: "missing"; display: string; original: null }
  | { kind: "invalid"; display: string; original: string }
  | { kind: "valid"; display: string; original: string }

export function formatMonitorTimestamp(
  value: string | null,
  options: { locale?: string | string[]; timeZone?: string } = {},
): MonitorTimestamp {
  if (value === null) return { kind: "missing", display: "—", original: null }

  const parsed = new Date(value)
  if (!Number.isFinite(parsed.getTime())) {
    return { kind: "invalid", display: "Unavailable", original: value }
  }

  try {
    const formatter = new Intl.DateTimeFormat(options.locale, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: options.timeZone,
    })
    return { kind: "valid", display: formatter.format(parsed), original: value }
  } catch {
    return { kind: "invalid", display: "Unavailable", original: value }
  }
}
