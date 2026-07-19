import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { listMonitors, type MonitorDto, type MonitorStatus } from "@/lib/monitor-api"
import { RecentMonitors } from "./recent-monitors"

vi.mock("@/lib/monitor-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/monitor-api")>()
  return { ...actual, listMonitors: vi.fn() }
})

const states: MonitorStatus[] = ["unknown", "up", "down", "paused"]
const monitors: MonitorDto[] = states.map((status) => ({
  id: `monitor-${status}`,
  name: `${status} API`,
  url: `https://${status}.example.com`,
  http_method: "GET",
  interval_seconds: 60,
  timeout_seconds: 10,
  expected_status_min: 200,
  expected_status_max: 399,
  failure_threshold: 3,
  recovery_threshold: 2,
  status,
  next_check_at: null,
  last_checked_at: status === "unknown" ? null : "2026-07-18T12:30:00Z",
  latest_response_time_ms: status === "up" ? 184 : null,
  latest_status_code: status === "up" ? 204 : null,
  latest_error_category: status === "down" ? "connection" : null,
}))

afterEach(() => {
  cleanup()
  vi.mocked(listMonitors).mockReset()
})

describe("RecentMonitors", () => {
  it("renders every backend state with shared visible text and details links", async () => {
    vi.mocked(listMonitors).mockResolvedValue({
      type: "success",
      data: { items: monitors, page: 1, page_size: 5, total: 4, pages: 1 },
    })
    const { container } = render(<RecentMonitors />)

    expect(await screen.findByText("Unknown")).toBeTruthy()
    for (const status of states) {
      const label = status[0].toUpperCase() + status.slice(1)
      expect(screen.getByText(label)).toBeTruthy()
      expect(screen.getByRole("link", { name: `${status} API` }).getAttribute("href")).toBe(`/monitors/monitor-${status}`)
    }
    expect(container.querySelectorAll("[data-slot='badge'] svg")).toHaveLength(4)
    expect(screen.getByText("184 ms")).toBeTruthy()
    expect(screen.getByText("HTTP 204")).toBeTruthy()
    expect(screen.getByText("Connection failure")).toBeTruthy()
    expect(screen.getByText("Not checked yet")).toBeTruthy()
    expect(screen.getAllByTitle("UTC: 2026-07-18T12:30:00Z").length).toBeGreaterThan(0)
    expect(listMonitors).toHaveBeenCalledWith(1, 5, { signal: expect.any(AbortSignal) })
  })
})
