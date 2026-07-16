// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest"
import {
  getRedirectUrl,
  unstable_doesMiddlewareMatch,
} from "next/experimental/testing/server"
import { NextRequest } from "next/server"

import { config, proxy } from "@/proxy"


afterEach(() => {
  vi.unstubAllGlobals()
})

describe("authentication route matcher", () => {
  it.each([
    "/dashboard",
    "/dashboard/activity",
    "/monitors",
    "/monitors/new",
    "/monitors/monitor-1",
    "/monitors/incidents",
    "/monitors/incidents/incident-1",
    "/login",
    "/register",
  ])("matches %s", (url) => {
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url })).toBe(true)
  })

  it.each(["/", "/auth-unavailable", "/health"])("does not match %s", (url) => {
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url })).toBe(false)
  })
})

describe("protected routes", () => {
  it("redirects before rendering when the session cookie is missing", async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)

    const response = await proxy(new NextRequest("https://app.example/monitors?status=down"))

    expect(getRedirectUrl(response)).toBe(
      "https://app.example/login?next=%2Fmonitors%3Fstatus%3Ddown",
    )
    expect(response.headers.get("cache-control")).toBe("no-store")
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("redirects a confirmed invalid session and clears its cookie", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, {
      status: 401,
      headers: { "set-cookie": "amp_session=\"\"; Max-Age=0; Path=/; HttpOnly" },
    })))
    const request = new NextRequest("https://app.example/dashboard", {
      headers: { cookie: "amp_session=expired-token" },
    })

    const response = await proxy(request)

    expect(getRedirectUrl(response)).toBe(
      "https://app.example/login?next=%2Fdashboard",
    )
    expect(response.headers.get("set-cookie")).toContain("Max-Age=0")
  })

  it("passes an authenticated request and forwards session renewal", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ id: "user-1", email: "user@example.com" }),
      {
        status: 200,
        headers: { "set-cookie": "amp_session=renewed-token; Max-Age=3600; Path=/; HttpOnly" },
      },
    ))
    vi.stubGlobal("fetch", fetchMock)
    const request = new NextRequest("https://app.example/monitors/monitor-1", {
      headers: { cookie: "amp_session=valid-token; theme=dark" },
    })

    const response = await proxy(request)

    expect(response.status).toBe(200)
    expect(response.headers.get("x-middleware-next")).toBe("1")
    expect(response.headers.get("set-cookie")).toContain("renewed-token")
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/auth/me",
      expect.objectContaining({
        method: "GET",
        headers: { Cookie: "amp_session=valid-token" },
        cache: "no-store",
        signal: expect.any(AbortSignal),
      }),
    )
  })

  it.each([
    ["network failure", vi.fn().mockRejectedValue(new Error("backend unavailable"))],
    ["service failure", vi.fn().mockResolvedValue(new Response(null, { status: 503 }))],
  ])("shows the unavailable route for %s without clearing the cookie", async (_label, fetchMock) => {
    vi.stubGlobal("fetch", fetchMock)
    const request = new NextRequest("https://app.example/monitors?status=down", {
      headers: { cookie: "amp_session=unverified-token" },
    })

    const response = await proxy(request)

    expect(getRedirectUrl(response)).toBe(
      "https://app.example/auth-unavailable?next=%2Fmonitors%3Fstatus%3Ddown",
    )
    expect(response.headers.get("set-cookie")).toBeNull()
    expect(response.headers.get("cache-control")).toBe("no-store")
  })
})

describe("guest routes", () => {
  it("renders the form without verification when no cookie exists", async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)

    const response = await proxy(new NextRequest("https://app.example/login?next=%2Fmonitors"))

    expect(response.headers.get("x-middleware-next")).toBe("1")
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("redirects an authenticated user to the safe destination", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, {
      status: 200,
      headers: { "set-cookie": "amp_session=renewed; Path=/; HttpOnly" },
    })))
    const request = new NextRequest("https://app.example/login?next=%2Fmonitors%3Fstatus%3Ddown", {
      headers: { cookie: "amp_session=valid-token" },
    })

    const response = await proxy(request)

    expect(getRedirectUrl(response)).toBe("https://app.example/monitors?status=down")
    expect(response.headers.get("set-cookie")).toContain("renewed")
  })

  it("falls back to the dashboard for an unsafe destination", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 200 })))
    const request = new NextRequest("https://app.example/register?next=https%3A%2F%2Fattacker.example", {
      headers: { cookie: "amp_session=valid-token" },
    })

    expect(getRedirectUrl(await proxy(request))).toBe("https://app.example/dashboard")
  })

  it("clears a confirmed invalid cookie and renders the form", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, {
      status: 401,
      headers: { "set-cookie": "amp_session=\"\"; Max-Age=0; Path=/; HttpOnly" },
    })))
    const request = new NextRequest("https://app.example/register?next=%2Fmonitors", {
      headers: { cookie: "amp_session=invalid-token" },
    })

    const response = await proxy(request)

    expect(response.headers.get("x-middleware-next")).toBe("1")
    expect(response.headers.get("set-cookie")).toContain("Max-Age=0")
  })

  it("shows the unavailable route without looping when verification fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 503 })))
    const request = new NextRequest("https://app.example/login?next=%2Fmonitors", {
      headers: { cookie: "amp_session=unverified-token" },
    })

    const response = await proxy(request)

    expect(getRedirectUrl(response)).toBe(
      "https://app.example/auth-unavailable?next=%2Fmonitors",
    )
    expect(response.headers.get("set-cookie")).toBeNull()
  })
})
