import { describe, expect, it } from "vitest"

import { formatMonitorErrorCategory, formatMonitorResponseTime, formatMonitorStatusCode } from "./monitor-result"

describe("monitor result formatting", () => {
  it("formats persisted response values and null placeholders", () => {
    expect(formatMonitorResponseTime(1_204)).toBe("1,204 ms")
    expect(formatMonitorResponseTime(null)).toBe("—")
    expect(formatMonitorStatusCode(503)).toBe("503")
    expect(formatMonitorStatusCode(null)).toBe("—")
  })

  it("maps normalized categories without exposing unknown backend text", () => {
    expect(formatMonitorErrorCategory("connection")).toBe("Connection failure")
    expect(formatMonitorErrorCategory("request_timeout")).toBe("Request timeout")
    expect(formatMonitorErrorCategory("provider-secret-value")).toBe("Monitoring error")
    expect(formatMonitorErrorCategory(null)).toBeNull()
  })
})
