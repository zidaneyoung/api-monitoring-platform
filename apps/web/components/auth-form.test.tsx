import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { AuthForm } from "@/components/auth-form"

const navigationMock = vi.hoisted(() => ({ replace: vi.fn(), refresh: vi.fn() }))

vi.mock("next/navigation", () => ({
  useRouter: () => navigationMock,
}))

const fetchMock = vi.fn()

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock)
  fetchMock.mockReset()
  navigationMock.replace.mockReset()
  navigationMock.refresh.mockReset()
})

afterEach(() => {
  cleanup()
  document.documentElement.classList.remove("dark")
  localStorage.clear()
  sessionStorage.clear()
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
    expect(email.getAttribute("autocapitalize")).toBe("none")
    expect(email.getAttribute("spellcheck")).toBe("false")
    expect(password.maxLength).toBe(128)
    fireEvent.change(email, { target: { value: "invalid" } })
    fireEvent.blur(email)
    const emailAlert = screen.getByText("Enter a valid email address.")
    expect(emailAlert.textContent).toContain("valid email")
    expect(email.getAttribute("aria-invalid")).toBe("true")
    expect(email.getAttribute("aria-describedby")).toBe(emailAlert.id)

    fireEvent.change(password, { target: { value: "monitor123" } })
    expect(submit.disabled).toBe(false)
    fireEvent.click(submit)
    expect(document.activeElement).toBe(email)
    fireEvent.click(toggle)
    expect(password.type).toBe("text")
    expect(toggle.getAttribute("aria-pressed")).toBe("true")
    expect(screen.getByRole("button", { name: "Hide password" })).toBeTruthy()
  })

  it("creates a login session and safely redirects on success", async () => {
    let completeRequest: (response: Response) => void = () => undefined
    fetchMock.mockReturnValue(new Promise<Response>((resolve) => { completeRequest = resolve }))
    render(<AuthForm mode="login" redirectTo="/monitors?state=ready" />)

    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "qa@example.com" },
    })
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "monitor123" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Log in" }))

    expect(screen.getByRole("button", { name: "Working…" }).getAttribute("disabled")).not.toBeNull()
    expect(screen.getByText("Signing in…")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Working…" }))
    expect(fetchMock).toHaveBeenCalledOnce()

    await act(async () => completeRequest(new Response(JSON.stringify({
      id: "user-1",
      email: "qa@example.com",
    }), { status: 200 })))
    expect(await screen.findByText("Signed in. Redirecting…")).toBeTruthy()
    expect(navigationMock.replace).toHaveBeenCalledWith("/monitors?state=ready")
    expect(navigationMock.refresh).toHaveBeenCalledOnce()
    expect(screen.getByRole("link", { name: "Create one" }).getAttribute("href")).toBe(
      "/register?next=%2Fmonitors%3Fstate%3Dready",
    )
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(options.credentials).toBe("include")
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })

  it("shows a generic invalid-credential response without redirecting", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({
      error: { code: "invalid_credentials", message: "Invalid email or password." },
    }), { status: 401, headers: { "Content-Type": "application/json" } }))
    render(<AuthForm mode="login" />)

    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "qa@example.com" } })
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong-password" } })
    fireEvent.click(screen.getByRole("button", { name: "Log in" }))

    const alert = await screen.findByText("Invalid email or password.")
    expect(document.activeElement).toBe(alert)
    expect(navigationMock.replace).not.toHaveBeenCalled()
  })

  it("requires registration details and matching passwords", () => {
    render(<AuthForm mode="register" />)

    expect(screen.queryByLabelText("Full name")).toBeNull()
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

  it("registers, creates a session, and redirects to the app", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({
      id: "user-2",
      email: "jane@example.com",
    }), { status: 201 }))
    render(<AuthForm mode="register" />)

    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "Jane@Example.COM" } })
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "monitor123" } })
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "monitor123" } })
    fireEvent.click(screen.getByRole("button", { name: "Create account" }))

    expect(await screen.findByText("Account created. Redirecting…")).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [registrationUrl, registrationOptions] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(registrationUrl).toBe("http://localhost:8000/auth/register")
    expect(registrationOptions.credentials).toBe("include")
    expect(registrationOptions.body).toBe(JSON.stringify({ email: "Jane@Example.COM", password: "monitor123" }))
    expect(navigationMock.replace).toHaveBeenCalledWith("/dashboard")
    expect(navigationMock.refresh).toHaveBeenCalledOnce()
  })

  it("stops loading when registration fails", async () => {
    fetchMock.mockRejectedValue(new Error("sensitive transport detail"))
    render(<AuthForm mode="register" />)

    expect(screen.queryByLabelText("Full name")).toBeNull()
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "jane@example.com" } })
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "monitor123" } })
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "monitor123" } })
    fireEvent.click(screen.getByRole("button", { name: "Create account" }))

    expect(await screen.findByText("Unable to reach the service. Check your connection and try again.")).toBeTruthy()
    expect((screen.getByLabelText("Email address") as HTMLInputElement).value).toBe("jane@example.com")
    expect((screen.getByLabelText("Password") as HTMLInputElement).value).toBe("monitor123")
    expect((screen.getByLabelText("Confirm password") as HTMLInputElement).value).toBe("monitor123")
    expect(screen.getByRole("button", { name: "Create account" }).getAttribute("disabled")).toBeNull()
    expect(navigationMock.replace).not.toHaveBeenCalled()
  })

  it("shows a safe field-specific backend registration error", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({
      error: {
        code: "email_exists",
        message: "An account with this email already exists.",
        fields: [{ field: "email", message: "An account with this email already exists." }],
      },
    }), { status: 409, headers: { "Content-Type": "application/json" } }))
    render(<AuthForm mode="register" />)

    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "jane@example.com" } })
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "monitor123" } })
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "monitor123" } })
    fireEvent.click(screen.getByRole("button", { name: "Create account" }))

    expect(await screen.findByText("An account with this email already exists.")).toBeTruthy()
    expect(screen.getByText("Fix the highlighted fields and try again.")).toBeTruthy()
    expect(document.activeElement).toBe(screen.getByLabelText("Email address"))
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "new@example.com" } })
    expect(screen.queryByText("An account with this email already exists.")).toBeNull()
  })

  it("distinguishes service unavailability from invalid credentials", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 503 }))
    render(<AuthForm mode="login" />)

    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "qa@example.com" } })
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "monitor123" } })
    fireEvent.click(screen.getByRole("button", { name: "Log in" }))

    expect(await screen.findByText("Authentication is temporarily unavailable. Try again.")).toBeTruthy()
    expect(screen.queryByText("Invalid email or password.")).toBeNull()
  })

  it("disables retries until the Retry-After countdown ends", async () => {
    vi.useFakeTimers()
    fetchMock.mockResolvedValue(new Response(null, {
      status: 429,
      headers: { "Retry-After": "2" },
    }))
    render(<AuthForm mode="login" />)

    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "qa@example.com" } })
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "monitor123" } })
    fireEvent.click(screen.getByRole("button", { name: "Log in" }))

    await act(async () => Promise.resolve())
    expect(screen.getByRole("button", { name: "Try again in 2s" }).getAttribute("disabled")).not.toBeNull()
    expect(screen.getByText(/Too many attempts\. Try again after/)).toBeTruthy()

    await act(async () => vi.advanceTimersByTimeAsync(2_000))
    expect(screen.getByRole("button", { name: "Log in" }).getAttribute("disabled")).toBeNull()
    expect(screen.getByText("You can try again now.")).toBeTruthy()
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
