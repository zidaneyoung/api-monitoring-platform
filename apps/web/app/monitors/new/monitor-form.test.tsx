import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { MonitorForm } from "./monitor-form"
import type { MonitorDto } from "@/lib/monitor-api"


const navigationMock = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }))

vi.mock("next/navigation", () => ({
  useRouter: () => navigationMock,
}))

const fetchMock = vi.fn()
const existingMonitor: MonitorDto = {
  id: "monitor-1",
  name: "Existing API",
  url: "https://example.com/current",
  http_method: "HEAD",
  interval_seconds: 300,
  timeout_seconds: 20,
  expected_status_min: 201,
  expected_status_max: 299,
  failure_threshold: 4,
  recovery_threshold: 5,
  status: "up",
  next_check_at: "2026-07-16T20:00:00Z",
  last_checked_at: null,
  latest_response_time_ms: null,
  latest_status_code: null,
}

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
      detail: {
        code: "unsafe_monitor_destination",
        message: "Monitor URL must resolve to a public destination.",
      },
    }), { status: 422 }))
    render(<MonitorForm />)
    fillRequiredFields()

    fireEvent.click(screen.getByRole("button", { name: "Create monitor" }))

    expect(await screen.findByText("Monitor URL must resolve to a public destination.")).toBeTruthy()
    expect(screen.getByLabelText("URL").getAttribute("aria-invalid")).toBe("true")
    expect(screen.getByLabelText("Name").getAttribute("aria-invalid")).toBe("false")
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

  it("prefills and submits the complete edit configuration", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({
      ...existingMonitor,
      name: "Updated API",
    }), { status: 200 }))
    render(<MonitorForm monitor={existingMonitor} />)

    expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("Existing API")
    expect((screen.getByLabelText("URL") as HTMLInputElement).value).toBe("https://example.com/current")
    expect((screen.getByLabelText("HTTP method") as HTMLSelectElement).value).toBe("HEAD")
    expect((screen.getByLabelText("Interval (seconds)") as HTMLInputElement).value).toBe("300")
    expect((screen.getByLabelText("Timeout (seconds)") as HTMLInputElement).value).toBe("20")
    expect((screen.getByLabelText("Minimum accepted status") as HTMLInputElement).value).toBe("201")
    expect((screen.getByLabelText("Maximum accepted status") as HTMLInputElement).value).toBe("299")
    expect((screen.getByLabelText("Failure threshold") as HTMLInputElement).value).toBe("4")
    expect((screen.getByLabelText("Recovery threshold") as HTMLInputElement).value).toBe("5")

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Updated API" } })
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Save changes" })))

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("http://localhost:8000/monitors/monitor-1")
    expect(options.method).toBe("PUT")
    expect(JSON.parse(String(options.body))).toMatchObject({
      name: "Updated API",
      url: "https://example.com/current",
      http_method: "HEAD",
      interval_seconds: 300,
    })
    expect(navigationMock.push).toHaveBeenCalledWith("/monitors/monitor-1")
    expect(navigationMock.refresh).toHaveBeenCalledOnce()
  })
})
