import { afterEach, describe, expect, it, vi } from "vitest"

import {
  getCurrentUser,
  loginUser,
  logoutUser,
  registerUser,
  safeAuthRedirect,
} from "@/lib/auth-api"


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
    ["/monitors/123?tab=checks", "/monitors/123?tab=checks"],
  ])("maps %s to %s", (destination, expected) => {
    expect(safeAuthRedirect(destination)).toBe(expected)
  })
})

describe("authentication request timeout", () => {
  it.each([
    ["login", loginUser],
    ["registration", registerUser],
  ])("stops a stalled %s request with a safe error", async (_label, request) => {
    const controller = new AbortController()
    const timeoutMock = vi.spyOn(AbortSignal, "timeout").mockReturnValue(controller.signal)
    vi.stubGlobal("fetch", vi.fn((_url: string, options: RequestInit) => new Promise<Response>((_resolve, reject) => {
      options.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))
    })))

    const result = request("user@example.com", "monitor123")
    controller.abort()

    await expect(result).resolves.toEqual([
      { field: "form", message: "Unable to reach the service. Try again." },
    ])
    expect(timeoutMock).toHaveBeenCalledWith(10_000)
  })
})

describe("getCurrentUser", () => {
  it("uses the HttpOnly cookie across navigation and refresh without web storage", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "user-1", email: "user@example.com" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "user-1", email: "user@example.com" }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    const navigationUser = await getCurrentUser()
    const refreshedUser = await getCurrentUser()

    expect(navigationUser).toEqual({ id: "user-1", email: "user@example.com" })
    expect(refreshedUser).toEqual(navigationUser)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    for (const [, options] of fetchMock.mock.calls as [string, RequestInit][]) {
      expect(options.credentials).toBe("include")
      expect(options.cache).toBe("no-store")
      expect(options.signal).toBeInstanceOf(AbortSignal)
    }
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })

  it("fails closed for an invalid or expired session", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: { code: "not_authenticated", message: "Authentication required." },
    }), { status: 401 })))

    expect(await getCurrentUser()).toBeNull()
  })

  it("stops a stalled current-user request after five seconds", async () => {
    const controller = new AbortController()
    const timeoutMock = vi.spyOn(AbortSignal, "timeout").mockReturnValue(controller.signal)
    vi.stubGlobal("fetch", vi.fn((_url: string, options: RequestInit) => new Promise<Response>((_resolve, reject) => {
      options.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))
    })))

    const result = getCurrentUser()
    controller.abort()

    await expect(result).resolves.toBeNull()
    expect(timeoutMock).toHaveBeenCalledWith(5_000)
  })
})

describe("logoutUser", () => {
  it("posts the HttpOnly session cookie to logout", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal("fetch", fetchMock)

    await logoutUser()

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
    ["server failure", vi.fn().mockResolvedValue(new Response(null, { status: 503 }))],
    ["network failure", vi.fn().mockRejectedValue(new Error("sensitive transport detail"))],
  ])("returns a controlled error for %s", async (_label, fetchMock) => {
    vi.stubGlobal("fetch", fetchMock)

    await expect(logoutUser()).rejects.toThrow("Unable to log out. Try again.")
  })

  it("stops a stalled logout request after five seconds", async () => {
    const controller = new AbortController()
    const timeoutMock = vi.spyOn(AbortSignal, "timeout").mockReturnValue(controller.signal)
    vi.stubGlobal("fetch", vi.fn((_url: string, options: RequestInit) => new Promise<Response>((_resolve, reject) => {
      options.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))
    })))

    const result = logoutUser()
    controller.abort()

    await expect(result).rejects.toThrow("Unable to log out. Try again.")
    expect(timeoutMock).toHaveBeenCalledWith(5_000)
  })
})
