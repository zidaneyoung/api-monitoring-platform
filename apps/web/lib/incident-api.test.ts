import { afterEach, describe, expect, it, vi } from "vitest"

import {
  formatIncidentDuration,
  getIncident,
  listAllActiveIncidents,
  listIncidents,
} from "@/lib/incident-api"


const listItem = {
  id: "incident-1",
  monitor_id: "monitor-1",
  monitor_name: "Public API",
  status: "open",
  opened_at: "2026-07-17T12:00:00Z",
  resolved_at: null,
  duration_seconds: 65,
  cause_category: "request_timeout",
  cause_message: "Monitor request timed out.",
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe("listIncidents", () => {
  it("requests an owned incident page without caching", async () => {
    const page = { items: [listItem], page: 2, page_size: 10, total: 11, pages: 2 }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(page), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await expect(listIncidents("open", 2, 10)).resolves.toEqual({ type: "success", data: page })
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("http://localhost:8000/incidents?status=open&page=2&page_size=10")
    expect(options.credentials).toBe("include")
    expect(options.cache).toBe("no-store")
  })

  it.each([
    [401, { type: "unauthenticated" }],
    [503, { type: "unavailable" }],
    [404, { type: "not_found" }],
  ])("maps list status %s without exposing response details", async (status, expected) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("sensitive detail", { status })))
    await expect(listIncidents("resolved", 1, 10)).resolves.toEqual(expected)
  })

  it("rejects malformed payloads and retries one transient read failure", async () => {
    const page = { items: [listItem], page: 1, page_size: 10, total: 1, pages: 1 }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(page), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await expect(listIncidents("open", 1, 10)).resolves.toEqual({ type: "success", data: page })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})

describe("listAllActiveIncidents", () => {
  it("loads every active incident page and returns a count matching the items", async () => {
    const secondItem = { ...listItem, id: "incident-2", monitor_name: "Billing API" }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [listItem], page: 1, page_size: 100, total: 2, pages: 2 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [secondItem], page: 2, page_size: 100, total: 2, pages: 2 }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await expect(listAllActiveIncidents()).resolves.toEqual({
      type: "success",
      data: { items: [listItem, secondItem], page: 1, page_size: 2, total: 2, pages: 1 },
    })
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "http://localhost:8000/incidents?status=open&page=1&page_size=100",
      "http://localhost:8000/incidents?status=open&page=2&page_size=100",
    ])
  })
})

describe("getIncident", () => {
  it("returns an owned safe detail response", async () => {
    const detail = {
      ...listItem,
      detected_at: "2026-07-17T12:00:00Z",
      monitor: { id: "monitor-1", name: "Public API" },
      triggering_check: null,
      recovery_check: null,
      events: [],
    }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(detail), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await expect(getIncident("incident/one")).resolves.toEqual({ type: "success", data: detail })
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("http://localhost:8000/incidents/incident%2Fone")
    expect(options.credentials).toBe("include")
  })

  it("rejects malformed detail responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "incident-1" }), { status: 200 })))
    await expect(getIncident("incident-1")).resolves.toEqual({ type: "unexpected_response" })
  })
})

describe("formatIncidentDuration", () => {
  it.each([
    [0, "0s"],
    [65, "1m 5s"],
    [181_800, "2d 2h 30m"],
    [-1, "0s"],
  ])("formats %s seconds as %s", (value, expected) => {
    expect(formatIncidentDuration(value)).toBe(expected)
  })
})
