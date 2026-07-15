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

describe("protected route matcher", () => {
  it.each([
    "/dashboard",
    "/dashboard/activity",
    "/monitors",
    "/monitors/new",
    "/monitors/monitor-1",
    "/monitors/incidents",
    "/monitors/incidents/incident-1",
  ])("matches %s", (url) => {
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url })).toBe(true)
  })

  it.each(["/", "/login", "/register", "/health"])("does not match %s", (url) => {
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url })).toBe(false)
  })
})

describe("proxy", () => {
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

  it("rejects an invalid or expired backend session and clears its cookie", async () => {
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
      }),
    )
  })

  it("fails closed when authentication cannot be verified", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("backend unavailable")))
    const request = new NextRequest("https://app.example/monitors", {
      headers: { cookie: "amp_session=unverified-token" },
    })

    const response = await proxy(request)

    expect(getRedirectUrl(response)).toBe(
      "https://app.example/login?next=%2Fmonitors",
    )
  })
})
