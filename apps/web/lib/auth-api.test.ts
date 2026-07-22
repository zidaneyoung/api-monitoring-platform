import { afterEach, describe, expect, it, vi } from "vitest"

import {
  getCurrentUser,
  loginUser,
  logoutUser,
  registerUser,
} from "@/lib/auth-api"
import { authRouteWithNext, safeAuthRedirect } from "@/lib/auth-redirect"


afterEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})


describe("safeAuthRedirect", () => {
  it.each([
    [undefined, "/dashboard"],
    ["https://attacker.example/path", "/dashboard"],
    ["//attacker.example/path", "/dashboard"],
    ["/\\attacker.example/path", "/dashboard"],
    ["/%2f%2fattacker.example/path", "/dashboard"],
    ["/%252f%252fattacker.example/path", "/dashboard"],
    ["/%5cattacker.example/path", "/dashboard"],
    ["/monitors/123?tab=checks", "/monitors/123?tab=checks"],
  ])("maps %s to %s", (destination, expected) => {
    expect(safeAuthRedirect(destination)).toBe(expected)
  })

  it("preserves the destination between guest routes", () => {
    expect(authRouteWithNext("/register", "/monitors?status=down")).toBe(
      "/register?next=%2Fmonitors%3Fstatus%3Ddown",
    )
    expect(authRouteWithNext("/login", "https://attacker.example")).toBe("/login")
  })
})

describe("credential outcomes", () => {
  it("returns a typed success with the safe public user", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      id: "user-1",
      email: "user@example.com",
    }), { status: 200 })))

    await expect(loginUser("user@example.com", "monitor123")).resolves.toEqual({
      type: "success",
      data: { id: "user-1", email: "user@example.com" },
    })
  })

  it.each([
    [401, { type: "invalid_credentials" }],
    [503, { type: "unavailable" }],
    [500, { type: "unexpected_response" }],
  ])("maps login status %s without exposing the response body", async (status, expected) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ error: { code: "internal_error", message: "sensitive internal detail" } }),
      { status },
    )))

    await expect(loginUser("user@example.com", "monitor123")).resolves.toEqual(expected)
  })

  it("returns safe field validation errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: {
        code: "validation_error",
        message: "Request validation failed.",
        fields: [{ field: "email", message: "Enter a valid email address." }],
      },
    }), { status: 422 })))

    await expect(registerUser("invalid", "monitor123")).resolves.toEqual({
      type: "validation",
      errors: [{ field: "email", message: "Enter a valid email address." }],
    })
  })

  it("maps duplicate registration to a controlled conflict", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 409 })))

    await expect(registerUser("user@example.com", "monitor123")).resolves.toEqual({
      type: "conflict",
      field: "email",
    })
  })

  it.each([
    ["17", 17],
    ["invalid", 60],
    [null, 60],
  ])("parses Retry-After %s safely", async (header, expected) => {
    const headers = new Headers()
    if (header !== null) headers.set("Retry-After", header)
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, {
      status: 429,
      headers,
    })))

    await expect(loginUser("user@example.com", "monitor123")).resolves.toEqual({
      type: "rate_limited",
      retryAfterSeconds: expected,
    })
  })

  it("rejects a malformed success response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ email: "user@example.com" }),
      { status: 200 },
    )))

    await expect(loginUser("user@example.com", "monitor123")).resolves.toEqual({
      type: "unexpected_response",
    })
  })

  it("distinguishes timeout from network failure", async () => {
    const timeoutFetch = vi.fn().mockRejectedValue(new DOMException("timed out", "TimeoutError"))
    vi.stubGlobal("fetch", timeoutFetch)
    await expect(loginUser("user@example.com", "monitor123")).resolves.toEqual({ type: "timeout" })

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network detail")))
    await expect(loginUser("user@example.com", "monitor123")).resolves.toEqual({ type: "network_error" })
  })

  it.each([
    ["login", loginUser],
    ["registration", registerUser],
  ])("bounds the %s request at ten seconds", async (_label, request) => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new DOMException("timed out", "TimeoutError")))
    const timeoutMock = vi.spyOn(AbortSignal, "timeout")

    await request("user@example.com", "monitor123")

    expect(timeoutMock).toHaveBeenCalledWith(10_000)
  })
})

describe("getCurrentUser", () => {
  it("uses the HttpOnly cookie across navigation without web storage", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      id: "user-1",
      email: "user@example.com",
    }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await expect(getCurrentUser()).resolves.toEqual({
      type: "success",
      data: { id: "user-1", email: "user@example.com" },
    })
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(options.credentials).toBe("include")
    expect(options.cache).toBe("no-store")
    expect(options.signal).toBeInstanceOf(AbortSignal)
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })

  it.each([
    [401, { type: "unauthenticated" }],
    [503, { type: "unavailable" }],
    [500, { type: "unexpected_response" }],
  ])("maps current-user status %s explicitly", async (status, expected) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status })))
    await expect(getCurrentUser()).resolves.toEqual(expected)
  })

  it("stops a stalled current-user request after five seconds", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new DOMException("timed out", "TimeoutError")))
    const timeoutMock = vi.spyOn(AbortSignal, "timeout")

    await expect(getCurrentUser()).resolves.toEqual({ type: "timeout" })
    expect(timeoutMock).toHaveBeenCalledWith(5_000)
  })
})

describe("logoutUser", () => {
  it("posts the HttpOnly session cookie to logout", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal("fetch", fetchMock)

    await expect(logoutUser()).resolves.toEqual({ type: "success" })

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/auth/logout",
      {
        method: "POST",
        credentials: "include",
        cache: "no-store",
        signal: expect.any(AbortSignal),
      },
    )
  })

  it.each([
    [503, { type: "cleared" }],
    [401, { type: "unauthenticated" }],
    [500, { type: "unexpected_response" }],
  ])("returns a safe outcome for status %s", async (status, expected) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status })))
    await expect(logoutUser()).resolves.toEqual(expected)
  })

  it("distinguishes a timeout from a network failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValueOnce(new DOMException("timed out", "TimeoutError")))
    await expect(logoutUser()).resolves.toEqual({ type: "timeout" })

    vi.stubGlobal("fetch", vi.fn().mockRejectedValueOnce(new Error("sensitive transport detail")))
    await expect(logoutUser()).resolves.toEqual({ type: "network_error" })
  })
})
