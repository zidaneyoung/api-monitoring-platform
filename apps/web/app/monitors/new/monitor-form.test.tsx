import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { MonitorForm } from "./monitor-form"


const navigationMock = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }))

vi.mock("next/navigation", () => ({
  useRouter: () => navigationMock,
}))

const fetchMock = vi.fn()

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock)
  fetchMock.mockReset()
  navigationMock.push.mockReset()
  navigationMock.refresh.mockReset()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function fillRequiredFields() {
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Public API" } })
  fireEvent.change(screen.getByLabelText("URL"), { target: { value: "https://example.com/health" } })
}

describe("MonitorForm", () => {
  it("renders all configuration fields with safe defaults", () => {
    render(<MonitorForm />)

    expect(screen.getByLabelText("Name")).toBeTruthy()
    expect(screen.getByLabelText("URL")).toBeTruthy()
    expect((screen.getByLabelText("HTTP method") as HTMLSelectElement).value).toBe("GET")
    expect((screen.getByLabelText("Interval (seconds)") as HTMLInputElement).value).toBe("60")
    expect((screen.getByLabelText("Timeout (seconds)") as HTMLInputElement).value).toBe("10")
    expect((screen.getByLabelText("Minimum accepted status") as HTMLInputElement).value).toBe("200")
    expect((screen.getByLabelText("Maximum accepted status") as HTMLInputElement).value).toBe("399")
    expect((screen.getByLabelText("Failure threshold") as HTMLInputElement).value).toBe("3")
    expect((screen.getByLabelText("Recovery threshold") as HTMLInputElement).value).toBe("2")
  })

  it("submits the authenticated request once and redirects to the list", async () => {
    let finishRequest: (response: Response) => void = () => undefined
    fetchMock.mockReturnValue(new Promise<Response>((resolve) => { finishRequest = resolve }))
    render(<MonitorForm />)
    fillRequiredFields()

    fireEvent.click(screen.getByRole("button", { name: "Create monitor" }))
    expect(screen.getByRole("button", { name: "Creating monitor…" }).hasAttribute("disabled")).toBe(true)
    fireEvent.click(screen.getByRole("button", { name: "Creating monitor…" }))
    expect(fetchMock).toHaveBeenCalledOnce()

    await act(async () => finishRequest(new Response(JSON.stringify({
      id: "monitor-1",
      name: "Public API",
      url: "https://example.com/health",
    }), { status: 201 })))
    expect(navigationMock.push).toHaveBeenCalledWith("/monitors")
    expect(navigationMock.refresh).toHaveBeenCalledOnce()
  })

  it("shows field-specific validation and preserves entered values", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({
      errors: [{ field: "url", message: "Enter a valid HTTP or HTTPS URL." }],
    }), { status: 422 }))
    render(<MonitorForm />)
    fillRequiredFields()

    fireEvent.click(screen.getByRole("button", { name: "Create monitor" }))

    expect(await screen.findByText("Enter a valid HTTP or HTTPS URL.")).toBeTruthy()
    expect(screen.getByLabelText("URL").getAttribute("aria-invalid")).toBe("true")
    expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("Public API")
    expect(navigationMock.push).not.toHaveBeenCalled()
  })

  it("shows a controlled service error and allows retry", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 503 }))
    render(<MonitorForm />)
    fillRequiredFields()

    fireEvent.click(screen.getByRole("button", { name: "Create monitor" }))

    expect(await screen.findByText("Monitor storage is temporarily unavailable. Try again.")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Create monitor" }).hasAttribute("disabled")).toBe(false)
    expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("Public API")
  })
})
