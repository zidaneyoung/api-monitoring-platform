import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { AuthForm } from "@/components/auth-form"

const fetchMock = vi.fn()

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock)
  fetchMock.mockReset()
})

afterEach(() => {
  cleanup()
  document.documentElement.classList.remove("dark")
  localStorage.clear()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe("AuthForm", () => {
  it("validates login fields and toggles password visibility", () => {
    render(<AuthForm mode="login" />)

    const email = screen.getByLabelText("Email address") as HTMLInputElement
    const password = screen.getByLabelText("Password") as HTMLInputElement
    const submit = screen.getByRole("button", { name: "Log in" }) as HTMLButtonElement
    const toggle = screen.getByRole("button", { name: "Show password" })

    expect(submit.disabled).toBe(true)
    fireEvent.change(email, { target: { value: "invalid" } })
    fireEvent.blur(email)
    expect(screen.getByRole("alert").textContent).toContain("valid email")

    fireEvent.change(password, { target: { value: "monitor123" } })
    expect(submit.disabled).toBe(false)
    fireEvent.click(toggle)
    expect(password.type).toBe("text")
    expect(toggle.getAttribute("aria-pressed")).toBe("true")
    expect(screen.getByRole("button", { name: "Hide password" })).toBeTruthy()
  })

  it("shows loading and success states for a valid mock login", () => {
    vi.useFakeTimers()
    render(<AuthForm mode="login" />)

    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "qa@example.com" },
    })
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "monitor123" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Log in" }))

    expect(screen.getByRole("button", { name: "Working…" }).getAttribute("disabled")).not.toBeNull()
    expect(screen.getByText("Submitting mock request…")).toBeTruthy()

    act(() => vi.advanceTimersByTime(1200))
    expect(screen.getByText("Mock login complete. No session was created.")).toBeTruthy()
  })

  it("requires registration details and matching passwords", () => {
    render(<AuthForm mode="register" />)

    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Jane Doe" } })
    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "jane@example.com" },
    })
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "monitor123" },
    })
    fireEvent.change(screen.getByLabelText("Confirm password"), {
      target: { value: "different" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Create account" }))

    expect(screen.getByText("Passwords do not match.")).toBeTruthy()
    expect(screen.getByText("Fix the highlighted fields and try again.")).toBeTruthy()
    expect(screen.getByRole("link", { name: "Log in" }).getAttribute("href")).toBe("/login")
  })

  it("submits registration to the backend and shows success", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ email: "jane@example.com" }), { status: 201 }))
    render(<AuthForm mode="register" />)

    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Jane Doe" } })
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "Jane@Example.COM" } })
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "monitor123" } })
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "monitor123" } })
    fireEvent.click(screen.getByRole("button", { name: "Create account" }))

    expect(await screen.findByText("Account created. You can now log in.")).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(options.credentials).toBe("include")
    expect(options.body).toBe(JSON.stringify({ email: "Jane@Example.COM", password: "monitor123" }))
  })

  it("shows a safe field-specific backend registration error", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({
      detail: { field: "email", message: "An account with this email already exists." },
    }), { status: 409, headers: { "Content-Type": "application/json" } }))
    render(<AuthForm mode="register" />)

    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Jane Doe" } })
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "jane@example.com" } })
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "monitor123" } })
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "monitor123" } })
    fireEvent.click(screen.getByRole("button", { name: "Create account" }))

    expect(await screen.findByText("An account with this email already exists.")).toBeTruthy()
    expect(screen.getByText("Fix the highlighted fields and try again.")).toBeTruthy()
  })

  it("toggles and persists the selected color theme", () => {
    render(<AuthForm mode="login" />)

    const toggle = screen.getByRole("button", { name: "Toggle color theme" })
    fireEvent.click(toggle)
    expect(document.documentElement.classList.contains("dark")).toBe(true)
    expect(localStorage.getItem("theme")).toBe("dark")

    fireEvent.click(toggle)
    expect(document.documentElement.classList.contains("dark")).toBe(false)
    expect(localStorage.getItem("theme")).toBe("light")
    expect(screen.getByRole("link", { name: "Create one" }).getAttribute("href")).toBe("/register")
  })
})
