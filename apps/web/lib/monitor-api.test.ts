import { afterEach, describe, expect, it, vi } from "vitest"

import { createMonitor, deleteMonitor, getMonitor, listMonitors, pauseMonitor, resumeMonitor, updateMonitor, type MonitorCreatePayload } from "@/lib/monitor-api"


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

  it("maps a blocked destination response to the URL field", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: {
        code: "unsafe_monitor_destination",
        message: "Monitor URL must resolve to a public destination.",
      },
    }), { status: 422 })))

    await expect(createMonitor(payload)).resolves.toEqual({
      type: "validation",
      errors: [{
        field: "url",
        message: "Monitor URL must resolve to a public destination.",
      }],
    })
  })

  it.each([
    [401, { type: "unauthenticated" }],
    [403, { type: "forbidden" }],
    [404, { type: "not_found" }],
    [409, { type: "conflict" }],
    [429, { type: "rate_limited" }],
    [503, { type: "unavailable" }],
    [500, { type: "internal_error" }],
    [400, { type: "unexpected_response" }],
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

describe("updateMonitor", () => {
  it("updates one monitor with the complete validated configuration", async () => {
    const updated = { ...responseMonitor, name: "Updated API", interval_seconds: 300 }
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify(updated),
      { status: 200 },
    ))
    vi.stubGlobal("fetch", fetchMock)

    await expect(updateMonitor("monitor/one", payload)).resolves.toEqual({
      type: "success",
      data: updated,
    })
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("http://localhost:8000/monitors/monitor%2Fone")
    expect(options.method).toBe("PUT")
    expect(options.credentials).toBe("include")
    expect(options.body).toBe(JSON.stringify(payload))
  })

  it("maps a blocked edited destination to the URL field", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: {
        code: "unsafe_monitor_destination",
        message: "Monitor URL must resolve to a public destination.",
      },
    }), { status: 422 })))

    await expect(updateMonitor("monitor-1", payload)).resolves.toEqual({
      type: "validation",
      errors: [{
        field: "url",
        message: "Monitor URL must resolve to a public destination.",
      }],
    })
  })

  it.each([
    [404, { type: "not_found" }],
    [401, { type: "unauthenticated" }],
    [503, { type: "unavailable" }],
  ])("maps update status %s to a controlled outcome", async (status, expected) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status })))
    await expect(updateMonitor("monitor-1", payload)).resolves.toEqual(expected)
  })
})

describe("listMonitors", () => {
  it("returns authenticated paginated monitor data", async () => {
    const page = { items: [responseMonitor], page: 2, page_size: 5, total: 6, pages: 2 }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(page), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await expect(listMonitors(2, 5)).resolves.toEqual({ type: "success", data: page })
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("http://localhost:8000/monitors?page=2&page_size=5")
    expect(options.credentials).toBe("include")
    expect(options.cache).toBe("no-store")
  })

  it.each([
    [401, { type: "unauthenticated" }],
    [503, { type: "unavailable" }],
    [500, { type: "internal_error" }],
  ])("maps list status %s to a controlled outcome", async (status, expected) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status })))
    await expect(listMonitors(1, 10)).resolves.toEqual(expected)
  })

  it("rejects malformed list responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      items: [{ id: "monitor-1" }], page: 1, page_size: 10, total: 1, pages: 1,
    }), { status: 200 })))
    await expect(listMonitors(1, 10)).resolves.toEqual({ type: "unexpected_response" })
  })

  it("retries one clearly transient read failure", async () => {
    const page = { items: [responseMonitor], page: 1, page_size: 10, total: 1, pages: 1 }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(page), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await expect(listMonitors(1, 10)).resolves.toEqual({ type: "success", data: page })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it.each([401, 403, 404, 409, 422, 429, 500])("does not retry non-transient read status %s", async (status) => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status }))
    vi.stubGlobal("fetch", fetchMock)

    await listMonitors(1, 10)
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it("cancels an in-flight read without retrying it", async () => {
    const controller = new AbortController()
    const fetchMock = vi.fn().mockImplementation((_url: string, options: RequestInit) => (
      new Promise<Response>((_resolve, reject) => {
        options.signal?.addEventListener("abort", () => reject(new DOMException("cancelled", "AbortError")))
      })
    ))
    vi.stubGlobal("fetch", fetchMock)

    const outcome = listMonitors(1, 10, { signal: controller.signal })
    controller.abort()

    await expect(outcome).resolves.toEqual({ type: "cancelled" })
    expect(fetchMock).toHaveBeenCalledOnce()
  })
})

describe("getMonitor", () => {
  it("returns one owned monitor without caching", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(responseMonitor), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await expect(getMonitor("monitor/one")).resolves.toEqual({
      type: "success",
      data: responseMonitor,
    })
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("http://localhost:8000/monitors/monitor%2Fone")
    expect(options.credentials).toBe("include")
    expect(options.cache).toBe("no-store")
  })

  it.each([
    [404, { type: "not_found" }],
    [401, { type: "unauthenticated" }],
    [503, { type: "unavailable" }],
    [500, { type: "internal_error" }],
  ])("maps detail status %s to a controlled outcome", async (status, expected) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status })))
    await expect(getMonitor("monitor-1")).resolves.toEqual(expected)
  })
})

describe("pauseMonitor", () => {
  it("pauses one monitor without sending configuration data", async () => {
    const paused = { ...responseMonitor, status: "paused", next_check_at: null }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(paused), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await expect(pauseMonitor("monitor/one")).resolves.toEqual({ type: "success", data: paused })
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("http://localhost:8000/monitors/monitor%2Fone/pause")
    expect(options.method).toBe("POST")
    expect(options.credentials).toBe("include")
    expect(options.body).toBeUndefined()
  })

  it.each([
    [404, { type: "not_found" }],
    [401, { type: "unauthenticated" }],
    [503, { type: "unavailable" }],
  ])("maps pause status %s to a controlled outcome", async (status, expected) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status })))
    await expect(pauseMonitor("monitor-1")).resolves.toEqual(expected)
  })
})

describe("resumeMonitor", () => {
  it("resumes one monitor without creating a client-side run", async () => {
    const resumed = { ...responseMonitor, status: "unknown", next_check_at: "2026-07-16T20:00:00Z" }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(resumed), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await expect(resumeMonitor("monitor/one")).resolves.toEqual({ type: "success", data: resumed })
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("http://localhost:8000/monitors/monitor%2Fone/resume")
    expect(options.method).toBe("POST")
    expect(options.body).toBeUndefined()
  })

  it.each([
    [404, { type: "not_found" }],
    [401, { type: "unauthenticated" }],
    [503, { type: "unavailable" }],
  ])("maps resume status %s to a controlled outcome", async (status, expected) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status })))
    await expect(resumeMonitor("monitor-1")).resolves.toEqual(expected)
  })
})

describe("deleteMonitor", () => {
  it("deletes one monitor without sending a request body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal("fetch", fetchMock)

    await expect(deleteMonitor("monitor/one")).resolves.toEqual({ type: "success", data: null })
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("http://localhost:8000/monitors/monitor%2Fone")
    expect(options.method).toBe("DELETE")
    expect(options.credentials).toBe("include")
    expect(options.body).toBeUndefined()
  })

  it.each([
    [404, { type: "not_found" }],
    [401, { type: "unauthenticated" }],
    [503, { type: "unavailable" }],
  ])("maps delete status %s to a controlled outcome", async (status, expected) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status })))
    await expect(deleteMonitor("monitor-1")).resolves.toEqual(expected)
  })
})

describe("mutation request policy", () => {
  it.each([
    ["create", () => createMonitor(payload)],
    ["edit", () => updateMonitor("monitor-1", payload)],
    ["pause", () => pauseMonitor("monitor-1")],
    ["resume", () => resumeMonitor("monitor-1")],
    ["delete", () => deleteMonitor("monitor-1")],
  ])("does not automatically retry %s", async (_name, mutate) => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 503 }))
    vi.stubGlobal("fetch", fetchMock)

    await mutate()
    expect(fetchMock).toHaveBeenCalledOnce()
  })
})
