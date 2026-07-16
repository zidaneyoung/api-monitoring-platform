import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { MonitorDetails } from "./monitor-details"
import type { MonitorDto } from "@/lib/monitor-api"


const fetchMock = vi.fn()

const monitor: MonitorDto = {
  id: "monitor-owned",
  name: "Owned details API",
  url: "https://example.com/health",
  http_method: "HEAD",
  interval_seconds: 300,
  timeout_seconds: 10,
  expected_status_min: 200,
  expected_status_max: 399,
  failure_threshold: 3,
  recovery_threshold: 2,
  status: "up",
  next_check_at: "2026-07-16T19:00:00Z",
  last_checked_at: "2026-07-16T18:55:00Z",
  latest_response_time_ms: 125,
  latest_status_code: 204,
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock)
  fetchMock.mockReset()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("MonitorDetails", () => {
  it("renders backend-authoritative configuration and latest state", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify(monitor), { status: 200 }))
    render(<MonitorDetails monitorId={monitor.id} />)

    expect(screen.getByText("Loading monitor details")).toBeTruthy()
    expect(await screen.findByText("Owned details API")).toBeTruthy()
    expect(screen.getAllByText("Up").length).toBeGreaterThan(0)
    expect(screen.getByText("HEAD")).toBeTruthy()
    expect(screen.getByText("5 minutes")).toBeTruthy()
    expect(screen.getByText("200–399")).toBeTruthy()
    expect(screen.getByText("125 ms")).toBeTruthy()
    expect(screen.getByText("204")).toBeTruthy()
    expect(screen.getByText("No check history loaded.")).toBeTruthy()
    expect(screen.getByRole("link", { name: "Edit" }).getAttribute("href")).toBe("/monitors/monitor-owned/edit")
    expect(screen.queryByText(/mock/i)).toBeNull()
  })

  it("renders the ownership-safe missing state", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 404 }))
    render(<MonitorDetails monitorId="missing-monitor" />)

    expect(await screen.findByText("Monitor not found")).toBeTruthy()
    expect(screen.getByText("This monitor does not exist or is not available to your account.")).toBeTruthy()
  })

  it("renders a controlled error and retries", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(monitor), { status: 200 }))
    render(<MonitorDetails monitorId={monitor.id} />)

    fireEvent.click(await screen.findByRole("button", { name: "Try again" }))
    expect(await screen.findByText("Owned details API")).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("confirms pause and immediately renders the persisted paused state", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true))
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify(monitor), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ...monitor,
        status: "paused",
        next_check_at: null,
      }), { status: 200 }))
    render(<MonitorDetails monitorId={monitor.id} />)

    fireEvent.click(await screen.findByRole("button", { name: "Pause monitor" }))
    const resume = await screen.findByRole("button", { name: "Resume monitor" })
    expect(resume.hasAttribute("disabled")).toBe(false)
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://localhost:8000/monitors/monitor-owned/pause")
  })

  it("resumes and immediately renders an active future schedule", async () => {
    const paused = { ...monitor, status: "paused", next_check_at: null }
    const resumed = {
      ...monitor,
      status: "unknown",
      next_check_at: "2026-07-16T20:01:00Z",
    }
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify(paused), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(resumed), { status: 200 }))
    render(<MonitorDetails monitorId={monitor.id} />)

    fireEvent.click(await screen.findByRole("button", { name: "Resume monitor" }))
    expect(await screen.findByRole("button", { name: "Pause monitor" })).toBeTruthy()
    expect(screen.getAllByText("Unknown").length).toBeGreaterThan(0)
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://localhost:8000/monitors/monitor-owned/resume")
  })
})
