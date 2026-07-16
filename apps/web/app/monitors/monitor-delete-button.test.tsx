import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { MonitorDeleteButton } from "./monitor-delete-button"
import type { MonitorDto } from "@/lib/monitor-api"


const fetchMock = vi.fn()
const onDeleted = vi.fn()
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
  onDeleted.mockReset()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("MonitorDeleteButton", () => {
  it("cancels without deleting or changing UI state", () => {
    vi.stubGlobal("confirm", vi.fn(() => false))
    render(<MonitorDeleteButton monitor={monitor} onDeleted={onDeleted} />)

    fireEvent.click(screen.getByRole("button", { name: "Delete monitor" }))
    expect(fetchMock).not.toHaveBeenCalled()
    expect(onDeleted).not.toHaveBeenCalled()
  })

  it("warns about history and reports a successful permanent delete", async () => {
    const confirmMock = vi.fn(() => true)
    vi.stubGlobal("confirm", confirmMock)
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }))
    render(<MonitorDeleteButton monitor={monitor} onDeleted={onDeleted} />)

    fireEvent.click(screen.getByRole("button", { name: "Delete monitor" }))
    await waitFor(() => expect(onDeleted).toHaveBeenCalledWith("monitor-1"))
    expect(confirmMock).toHaveBeenCalledWith(expect.stringContaining("checks and incident history"))
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it("shows a controlled error and remains retryable", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true))
    fetchMock.mockResolvedValue(new Response(null, { status: 503 }))
    render(<MonitorDeleteButton monitor={monitor} onDeleted={onDeleted} />)

    fireEvent.click(screen.getByRole("button", { name: "Delete monitor" }))
    expect(await screen.findByText("The monitor could not be deleted. Try again.")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Delete monitor" }).hasAttribute("disabled")).toBe(false)
  })
})
