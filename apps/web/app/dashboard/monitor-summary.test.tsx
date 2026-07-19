import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { getMonitorSummary } from "@/lib/monitor-api"
import { MonitorSummary } from "./monitor-summary"

vi.mock("@/lib/monitor-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/monitor-api")>()
  return { ...actual, getMonitorSummary: vi.fn() }
})

afterEach(() => {
  cleanup()
  vi.mocked(getMonitorSummary).mockReset()
})

describe("MonitorSummary", () => {
  it("loads and renders every backend-authoritative state count", async () => {
    vi.mocked(getMonitorSummary).mockResolvedValue({
      type: "success",
      data: { total: 10, up: 4, down: 2, paused: 1, unknown: 3 },
    })
    render(<MonitorSummary />)

    expect(screen.getByRole("status").getAttribute("aria-busy")).toBe("true")
    expect(await screen.findByText("10", { selector: "[data-slot='card-title']" })).toBeTruthy()
    expect(screen.getByText("Up").parentElement?.textContent).toContain("4")
    expect(screen.getByText("Down").parentElement?.textContent).toContain("2")
    expect(screen.getByText("Paused").parentElement?.textContent).toContain("1")
    expect(screen.getByText("Unknown").parentElement?.textContent).toContain("3")
  })

  it("renders a controlled error and retries", async () => {
    vi.mocked(getMonitorSummary)
      .mockResolvedValueOnce({ type: "unavailable" })
      .mockResolvedValueOnce({
        type: "success",
        data: { total: 0, up: 0, down: 0, paused: 0, unknown: 0 },
      })
    render(<MonitorSummary />)

    expect(await screen.findByRole("alert", { name: "Unable to load monitor summary" })).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Try again" }))
    await waitFor(() => expect(getMonitorSummary).toHaveBeenCalledTimes(2))
    expect((await screen.findByText("Monitors")).parentElement?.textContent).toContain("0")
  })
})
