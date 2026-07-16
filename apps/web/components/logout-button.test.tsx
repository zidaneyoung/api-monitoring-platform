import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { LogoutButton } from "@/components/logout-button"


const replace = vi.fn()
const refresh = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, refresh }),
}))

afterEach(() => {
  cleanup()
  replace.mockReset()
  refresh.mockReset()
  vi.unstubAllGlobals()
})

describe("LogoutButton", () => {
  it("logs out with the session cookie and redirects to login", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal("fetch", fetchMock)
    render(<LogoutButton />)

    fireEvent.click(screen.getByRole("button", { name: "Log out" }))

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"))
    expect(refresh).toHaveBeenCalledOnce()
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

  it("navigates after a controlled response clears the cookie", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 503 })))
    render(<LogoutButton />)

    fireEvent.click(screen.getByRole("button", { name: "Log out" }))

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"))
    expect(refresh).toHaveBeenCalledOnce()
  })

  it.each([
    [new DOMException("timed out", "TimeoutError"), "Logout timed out. Your session may still be active. Try again."],
    [new Error("sensitive network detail"), "Unable to reach the service. Your session may still be active. Try again."],
  ])("stays in place when logout is not confirmed", async (failure, message) => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(failure))
    render(<LogoutButton />)

    fireEvent.click(screen.getByRole("button", { name: "Log out" }))

    expect((await screen.findByRole("alert")).textContent).toBe(message)
    expect(replace).not.toHaveBeenCalled()
    expect((screen.getByRole("button", { name: "Log out" }) as HTMLButtonElement).disabled).toBe(false)
  })

  it("prevents repeated activation while logout is pending", async () => {
    let completeRequest: (response: Response) => void = () => undefined
    const fetchMock = vi.fn().mockReturnValue(new Promise<Response>((resolve) => {
      completeRequest = resolve
    }))
    vi.stubGlobal("fetch", fetchMock)
    render(<LogoutButton />)

    const button = screen.getByRole("button", { name: "Log out" })
    fireEvent.click(button)
    fireEvent.click(button)

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(screen.getByRole("button", { name: "Logging out" }).getAttribute("aria-busy")).toBe("true")
    completeRequest(new Response(null, { status: 204 }))
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"))
  })
})
