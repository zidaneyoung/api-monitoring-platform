import { afterEach, describe, expect, it, vi } from "vitest"

import { createMonitor, type MonitorCreatePayload } from "@/lib/monitor-api"


const payload: MonitorCreatePayload = {
  name: "Public API",
  url: "https://example.com/health",
  http_method: "GET",
  interval_seconds: 60,
  timeout_seconds: 10,
  expected_status_min: 200,
  expected_status_max: 399,
  failure_threshold: 3,
  recovery_threshold: 2,
}

const responseMonitor = {
  id: "monitor-1",
  ...payload,
  status: "unknown",
  next_check_at: "2026-07-16T18:00:00Z",
  last_checked_at: null,
  latest_response_time_ms: null,
  latest_status_code: null,
}

afterEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe("createMonitor", () => {
  it("creates a monitor with credentials and returns public data", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify(responseMonitor),
      { status: 201 },
    ))
    vi.stubGlobal("fetch", fetchMock)

    await expect(createMonitor(payload)).resolves.toEqual({
      type: "success",
      data: responseMonitor,
    })
    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("http://localhost:8000/monitors")
    expect(options.credentials).toBe("include")
    expect(options.body).toBe(JSON.stringify(payload))
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })

  it("returns safe field validation errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      errors: [{ field: "url", message: "Enter a valid HTTP or HTTPS URL." }],
    }), { status: 422 })))

    await expect(createMonitor(payload)).resolves.toEqual({
      type: "validation",
      errors: [{ field: "url", message: "Enter a valid HTTP or HTTPS URL." }],
    })
  })

  it.each([
    [401, { type: "unauthenticated" }],
    [503, { type: "unavailable" }],
    [500, { type: "unexpected_response" }],
  ])("maps status %s without exposing response details", async (status, expected) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: "sensitive internal detail" }),
      { status },
    )))
    await expect(createMonitor(payload)).resolves.toEqual(expected)
  })

  it.each([
    [new DOMException("timed out", "TimeoutError"), { type: "timeout" }],
    [new Error("sensitive network detail"), { type: "network_error" }],
  ])("maps request failure to a controlled outcome", async (failure, expected) => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(failure))
    await expect(createMonitor(payload)).resolves.toEqual(expected)
  })
})
