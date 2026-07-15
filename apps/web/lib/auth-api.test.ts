import { afterEach, describe, expect, it, vi } from "vitest"

import { getCurrentUser, safeAuthRedirect } from "@/lib/auth-api"


afterEach(() => {
  localStorage.clear()
  sessionStorage.clear()
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
})
