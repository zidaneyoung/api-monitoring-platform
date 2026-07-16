import { act, cleanup, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { AppShell } from "@/components/app-shell"


const navigationMock = vi.hoisted(() => ({
  pathname: "/monitors",
  replace: vi.fn(),
  refresh: vi.fn(),
}))

vi.mock("next/navigation", () => ({
  usePathname: () => navigationMock.pathname,
  useRouter: () => navigationMock,
}))

const fetchMock = vi.fn()

beforeEach(() => {
  navigationMock.pathname = "/monitors"
  navigationMock.replace.mockReset()
  navigationMock.refresh.mockReset()
  fetchMock.mockReset()
  vi.stubGlobal("fetch", fetchMock)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("AppShell current user", () => {
  it("shows a neutral shell until the real user resolves", async () => {
    let completeRequest: (response: Response) => void = () => undefined
    fetchMock.mockReturnValue(new Promise<Response>((resolve) => {
      completeRequest = resolve
    }))

    render(<AppShell><p>Sensitive protected content</p></AppShell>)

    expect(screen.getByRole("status", { name: "Loading account" })).toBeTruthy()
    expect(screen.queryByText("Sensitive protected content")).toBeNull()
    expect(screen.queryByText("Zidane Young")).toBeNull()
    expect(screen.queryByText("ZY")).toBeNull()

    await act(async () => completeRequest(new Response(JSON.stringify({
      id: "user-1",
      email: "zidane.young@example.com",
    }), { status: 200 })))

    expect(await screen.findByText("zidane.young@example.com")).toBeTruthy()
    expect(screen.getByText("ZY")).toBeTruthy()
    expect(screen.getByText("Sensitive protected content")).toBeTruthy()
  })

  it("retains the current user across protected client navigation", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({
      id: "user-2",
      email: "qa@example.com",
    }), { status: 200 }))

    const view = render(<AppShell><p>Monitors</p></AppShell>)
    expect(await screen.findByText("qa@example.com")).toBeTruthy()

    navigationMock.pathname = "/dashboard"
    view.rerender(<AppShell><p>Dashboard</p></AppShell>)

    expect(screen.getByText("Dashboard", { selector: "p" })).toBeTruthy()
    expect(screen.getByText("qa@example.com")).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it("redirects only a confirmed unauthenticated session to login", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 401 }))
    render(<AppShell><p>Sensitive protected content</p></AppShell>)

    await waitFor(() => expect(navigationMock.replace).toHaveBeenCalledWith(
      "/login?next=%2Fmonitors",
    ))
    expect(screen.queryByText("Sensitive protected content")).toBeNull()
  })

  it("uses the unavailable state for temporary verification failures", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 503 }))
    render(<AppShell><p>Sensitive protected content</p></AppShell>)

    await waitFor(() => expect(navigationMock.replace).toHaveBeenCalledWith(
      "/auth-unavailable?next=%2Fmonitors",
    ))
    expect(screen.queryByText("Sensitive protected content")).toBeNull()
  })

  it("does not request or render the application shell on guest routes", () => {
    navigationMock.pathname = "/login"
    render(<AppShell><p>Login form</p></AppShell>)

    expect(screen.getByText("Login form")).toBeTruthy()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
