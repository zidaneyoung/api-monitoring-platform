import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { listAllActiveIncidents, type IncidentListDto } from "@/lib/incident-api"
import { ActiveIncidents } from "./active-incidents"

vi.mock("@/lib/incident-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/incident-api")>()
  return { ...actual, listAllActiveIncidents: vi.fn() }
})

function activePage(): IncidentListDto {
  return {
    items: [
      {
        id: "incident-1",
        monitor_id: "monitor-1",
        monitor_name: "Public API",
        status: "open",
        opened_at: "2026-07-17T12:00:00Z",
        resolved_at: null,
        duration_seconds: 7_382,
        cause_category: "request_timeout",
        cause_message: "Monitor request timed out.",
      },
      {
        id: "incident-2",
        monitor_id: "monitor-2",
        monitor_name: "Billing API",
        status: "acknowledged",
        opened_at: "2026-07-17T13:00:00Z",
        resolved_at: null,
        duration_seconds: 3_600,
        cause_category: "http_status",
        cause_message: "Monitor returned an unexpected status.",
      },
    ],
    page: 1,
    page_size: 2,
    total: 2,
    pages: 1,
  }
}

afterEach(() => {
  cleanup()
  vi.mocked(listAllActiveIncidents).mockReset()
})

describe("ActiveIncidents", () => {
  it("shows every active item with an agreeing count, monitor, opening, current duration, and details link", async () => {
    vi.mocked(listAllActiveIncidents).mockResolvedValue({ type: "success", data: activePage() })
    render(<ActiveIncidents />)

    expect(await screen.findByText("2 active incidents displayed.")).toBeTruthy()
    const links = screen.getAllByRole("link")
    expect(links).toHaveLength(2)
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "/monitors/incidents/incident-1",
      "/monitors/incidents/incident-2",
    ])
    expect(within(links[0]).getByText("Public API")).toBeTruthy()
    expect(within(links[0]).getByText("Opened")).toBeTruthy()
    expect(within(links[0]).getByTitle("UTC: 2026-07-17T12:00:00Z")).toBeTruthy()
    expect(within(links[0]).getByText("Current duration")).toBeTruthy()
    expect(within(links[0]).getByText("2h 3m")).toBeTruthy()
  })

  it("shows a clear empty state", async () => {
    vi.mocked(listAllActiveIncidents).mockResolvedValue({ type: "success", data: { ...activePage(), items: [], page_size: 1, total: 0 } })
    render(<ActiveIncidents />)

    expect(await screen.findByRole("status", { name: "No active incidents" })).toBeTruthy()
    expect(screen.getByText("0 active incidents displayed.")).toBeTruthy()
  })

  it("shows a controlled error and retries", async () => {
    vi.mocked(listAllActiveIncidents)
      .mockResolvedValueOnce({ type: "unavailable" })
      .mockResolvedValueOnce({ type: "success", data: activePage() })
    render(<ActiveIncidents />)

    fireEvent.click(await screen.findByRole("button", { name: "Try again" }))
    await waitFor(() => expect(listAllActiveIncidents).toHaveBeenCalledTimes(2))
    expect(await screen.findByText("2 active incidents displayed.")).toBeTruthy()
  })
})
