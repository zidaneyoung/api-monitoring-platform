import { describe, expect, it } from "vitest"

import { formatMonitorTimestamp, parseApiTimestamp } from "./monitor-time"


describe("formatMonitorTimestamp", () => {
  it("converts UTC API timestamps for the selected browser-local timezone", () => {
    expect(formatMonitorTimestamp("2026-07-16T18:00:00Z", {
      locale: "en-US",
      timeZone: "America/New_York",
    })).toEqual({
      kind: "valid",
      display: "Jul 16, 2026, 2:00 PM",
      original: "2026-07-16T18:00:00Z",
    })
  })

  it("keeps the original offset timestamp while formatting its instant", () => {
    const formatted = formatMonitorTimestamp("2026-07-16T18:00:00+02:00", {
      locale: "en-US",
      timeZone: "UTC",
    })
    expect(formatted.display).toBe("Jul 16, 2026, 4:00 PM")
    expect(formatted.original).toBe("2026-07-16T18:00:00+02:00")
  })

  it("converts one UTC instant across date boundaries in two display timezones", () => {
    const source = "2026-01-01T01:30:00Z"
    expect(formatMonitorTimestamp(source, {
      locale: "en-US",
      timeZone: "America/Los_Angeles",
    }).display).toBe("Dec 31, 2025, 5:30 PM")
    expect(formatMonitorTimestamp(source, {
      locale: "en-US",
      timeZone: "Asia/Tokyo",
    }).display).toBe("Jan 1, 2026, 10:30 AM")
    expect(source).toBe("2026-01-01T01:30:00Z")
  })

  it("rejects naive timestamps instead of silently parsing them as local time", () => {
    expect(parseApiTimestamp("2026-07-16T18:00:00")).toBeNull()
    expect(formatMonitorTimestamp("2026-07-16T18:00:00")).toEqual({
      kind: "invalid",
      display: "Unavailable",
      original: "2026-07-16T18:00:00",
    })
  })

  it("handles missing and invalid values without throwing", () => {
    expect(formatMonitorTimestamp(null)).toEqual({ kind: "missing", display: "—", original: null })
    expect(formatMonitorTimestamp("not-a-timestamp")).toEqual({
      kind: "invalid",
      display: "Unavailable",
      original: "not-a-timestamp",
    })
  })
})
