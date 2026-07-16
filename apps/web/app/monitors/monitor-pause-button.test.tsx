import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { MonitorStateButton } from "./monitor-pause-button"
import type { MonitorDto } from "@/lib/monitor-api"


const fetchMock = vi.fn()
const onChanged = vi.fn()
const monitor: MonitorDto = {
  id: "monitor-1",
  name: "Public API",
  url: "https://example.com",
  http_method: "GET",
  interval_seconds: 60,
  timeout_seconds: 10,
  expected_status_min: 200,
  expected_status_max: 399,
  failure_threshold: 3,
  recovery_threshold: 2,
  status: "up",
  next_check_at: "2026-07-16T20:00:00Z",
  last_checked_at: null,
  latest_response_time_ms: null,
  latest_status_code: null,
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock)
  fetchMock.mockReset()
  onChanged.mockReset()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("MonitorStateButton", () => {
  it("cancels without changing the monitor", () => {
    vi.stubGlobal("confirm", vi.fn(() => false))
    render(<MonitorStateButton monitor={monitor} onChanged={onChanged} />)

    fireEvent.click(screen.getByRole("button", { name: "Pause monitor" }))
    expect(fetchMock).not.toHaveBeenCalled()
    expect(onChanged).not.toHaveBeenCalled()
  })

  it("confirms, pauses once, and reports the new state", async () => {
    const paused = { ...monitor, status: "paused", next_check_at: null }
    vi.stubGlobal("confirm", vi.fn(() => true))
    fetchMock.mockResolvedValue(new Response(JSON.stringify(paused), { status: 200 }))
    render(<MonitorStateButton monitor={monitor} onChanged={onChanged} />)

    fireEvent.click(screen.getByRole("button", { name: "Pause monitor" }))
    expect(await screen.findByRole("button", { name: "Pause monitor" })).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledOnce()
    expect(onChanged).toHaveBeenCalledWith(paused)
  })

  it("keeps the action available after a controlled failure", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true))
    fetchMock.mockResolvedValue(new Response(null, { status: 503 }))
    render(<MonitorStateButton monitor={monitor} onChanged={onChanged} />)

    fireEvent.click(screen.getByRole("button", { name: "Pause monitor" }))
    expect(await screen.findByText("The monitor could not be paused. Try again.")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Pause monitor" }).hasAttribute("disabled")).toBe(false)
  })

  it("resumes immediately without a second confirmation", async () => {
    const paused: MonitorDto = { ...monitor, status: "paused", next_check_at: null }
    const resumed: MonitorDto = {
      ...monitor,
      status: "unknown",
      next_check_at: "2026-07-16T20:01:00Z",
    }
    const confirmMock = vi.fn()
    vi.stubGlobal("confirm", confirmMock)
    fetchMock.mockResolvedValue(new Response(JSON.stringify(resumed), { status: 200 }))
    render(<MonitorStateButton monitor={paused} onChanged={onChanged} />)

    fireEvent.click(screen.getByRole("button", { name: "Resume monitor" }))
    expect(await screen.findByRole("button", { name: "Resume monitor" })).toBeTruthy()
    expect(confirmMock).not.toHaveBeenCalled()
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://localhost:8000/monitors/monitor-1/resume")
    expect(onChanged).toHaveBeenCalledWith(resumed)
  })
})
