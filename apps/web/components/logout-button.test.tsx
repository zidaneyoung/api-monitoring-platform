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
    render(<LogoutButton>Account</LogoutButton>)

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

  it("stays in place and reports a controlled failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 503 })))
    render(<LogoutButton>Account</LogoutButton>)

    fireEvent.click(screen.getByRole("button", { name: "Log out" }))

    const status = await screen.findByText("Unable to log out. Try again.")
    expect(status.textContent).toBe("Unable to log out. Try again.")
    expect(replace).not.toHaveBeenCalled()
    expect((screen.getByRole("button", { name: "Log out" }) as HTMLButtonElement).disabled).toBe(false)
  })
})
