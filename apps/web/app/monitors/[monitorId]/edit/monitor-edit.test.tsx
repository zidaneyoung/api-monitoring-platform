import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { MonitorEdit } from "./monitor-edit"
import type { MonitorDto } from "@/lib/monitor-api"


const navigationMock = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }))

vi.mock("next/navigation", () => ({
  useRouter: () => navigationMock,
}))

const fetchMock = vi.fn()
const returnHref = "/monitors?page=2&page_size=25"
const monitor: MonitorDto = {
  id: "monitor-owned",
  name: "Current monitor name",
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
  last_checked_at: null,
  latest_response_time_ms: null,
  latest_status_code: null,
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock)
  fetchMock.mockReset()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("MonitorEdit", () => {
  it("loads the owner monitor and renders every current value", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify(monitor), { status: 200 }))
    render(<MonitorEdit monitorId={monitor.id} returnHref={returnHref} />)

    expect(screen.getByText("Loading monitor configuration")).toBeTruthy()
    expect(await screen.findByText("Edit monitor")).toBeTruthy()
    expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("Current monitor name")
    expect((screen.getByLabelText("URL") as HTMLInputElement).value).toBe("https://example.com/health")
    expect((screen.getByLabelText("HTTP method") as HTMLSelectElement).value).toBe("HEAD")
    expect((screen.getByLabelText("Interval (seconds)") as HTMLInputElement).value).toBe("300")
    expect(screen.getByRole("link", { name: "Back to monitor" }).getAttribute("href")).toBe("/monitors/monitor-owned?return_to=%2Fmonitors%3Fpage%3D2%26page_size%3D25")
  })

  it("renders the ownership-safe missing state", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 404 }))
    render(<MonitorEdit monitorId="missing" returnHref={returnHref} />)
    expect(await screen.findByText("Monitor not found")).toBeTruthy()
    expect(screen.getByText("This monitor does not exist or is not available to your account.")).toBeTruthy()
  })

  it("renders a controlled load error and retries", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(null, { status: 500 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(monitor), { status: 200 }))
    render(<MonitorEdit monitorId={monitor.id} returnHref={returnHref} />)

    fireEvent.click(await screen.findByRole("button", { name: "Try again" }))
    expect(await screen.findByDisplayValue("Current monitor name")).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
