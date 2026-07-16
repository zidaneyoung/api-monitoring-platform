import { describe, expect, it } from "vitest"

import { formatMonitorTimestamp } from "./monitor-time"


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

  it("handles missing and invalid values without throwing", () => {
    expect(formatMonitorTimestamp(null)).toEqual({ kind: "missing", display: "—", original: null })
    expect(formatMonitorTimestamp("not-a-timestamp")).toEqual({
      kind: "invalid",
      display: "Unavailable",
      original: "not-a-timestamp",
    })
  })
})
