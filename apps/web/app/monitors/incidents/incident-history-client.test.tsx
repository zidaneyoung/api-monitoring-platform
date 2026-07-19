import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { listIncidents, type IncidentListDto, type IncidentListItemDto, type IncidentSection } from "@/lib/incident-api"
import { IncidentHistoryClient } from "./incident-history-client"

vi.mock("@/lib/incident-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/incident-api")>()
  return { ...actual, listIncidents: vi.fn() }
})

const active: IncidentListItemDto = {
  id: "active-1",
  monitor_id: "monitor-active",
  monitor_name: "Active API",
  status: "open",
  opened_at: "2026-07-10T15:00:00Z",
  resolved_at: null,
  duration_seconds: 7_200,
  cause_category: "request_timeout",
  cause_message: "Monitor request timed out.",
}

const newestResolved: IncidentListItemDto = {
  id: "resolved-newest",
  monitor_id: "monitor-newest",
  monitor_name: "Newest resolved API",
  status: "resolved",
  opened_at: "2026-07-10T14:00:00Z",
  resolved_at: "2026-07-10T14:03:00Z",
  duration_seconds: 180,
  cause_category: "http_status",
  cause_message: "Monitor returned an unexpected status.",
}

const olderResolved: IncidentListItemDto = {
  ...newestResolved,
  id: "resolved-older",
  monitor_id: "monitor-older",
  monitor_name: "Older resolved API",
  opened_at: "2026-07-10T13:00:00Z",
  resolved_at: "2026-07-10T13:02:00Z",
  duration_seconds: 120,
}

function page(items: IncidentListItemDto[], requestedPage = 1, pages = 1, total = items.length): IncidentListDto {
  return { items, page: requestedPage, page_size: 10, total, pages }
}

afterEach(() => {
  cleanup()
  vi.mocked(listIncidents).mockReset()
})

describe("IncidentHistoryClient resolved incidents", () => {
  it("shows only resolved items in consistent order with opening, resolution, and final duration", async () => {
    vi.mocked(listIncidents).mockImplementation(async (section: IncidentSection) => ({
      type: "success",
      data: section === "open" ? page([active]) : page([newestResolved, olderResolved]),
    }))
    render(<IncidentHistoryClient />)

    await screen.findByText("Newest resolved API")
    fireEvent.change(screen.getByLabelText("Filter by incident status"), { target: { value: "resolved" } })
    expect(screen.queryByText("Open incidents")).toBeNull()
    const links = screen.getAllByRole("link")
    expect(links.map((link) => link.textContent)).toEqual(["http status", "http status"])
    const records = document.querySelectorAll(".incident-record")
    expect(records).toHaveLength(2)
    expect(within(records[0] as HTMLElement).getByText("Newest resolved API")).toBeTruthy()
    expect(within(records[0] as HTMLElement).getByText("Opened")).toBeTruthy()
    expect(within(records[0] as HTMLElement).getByText("Resolved")).toBeTruthy()
    expect(within(records[0] as HTMLElement).getByText("Final duration")).toBeTruthy()
    expect(within(records[0] as HTMLElement).getByText("3m 0s")).toBeTruthy()
    expect(links[0].getAttribute("href")).toBe("/monitors/incidents/resolved-newest")
  })

  it("loads the next resolved page without mixing active incidents", async () => {
    const firstPageItems = [
      newestResolved,
      ...Array.from({ length: 9 }, (_, index) => ({
        ...newestResolved,
        id: `resolved-filler-${index}`,
        monitor_id: `monitor-filler-${index}`,
        monitor_name: `Resolved filler ${index}`,
      })),
    ]
    vi.mocked(listIncidents).mockImplementation(async (section: IncidentSection, requestedPage) => ({
      type: "success",
      data: section === "open"
        ? page([active])
        : requestedPage === 1
          ? page(firstPageItems, 1, 2, 11)
          : page([olderResolved], 2, 2, 11),
    }))
    render(<IncidentHistoryClient />)

    await screen.findByText("Newest resolved API")
    fireEvent.change(screen.getByLabelText("Filter by incident status"), { target: { value: "resolved" } })
    fireEvent.click(screen.getByRole("button", { name: "Next page" }))
    expect(await screen.findByText("Older resolved API")).toBeTruthy()
    expect(screen.queryByText("Active API")).toBeNull()
    await waitFor(() => expect(listIncidents).toHaveBeenCalledWith("resolved", 2, 10, { signal: expect.any(AbortSignal) }))
    expect(screen.getByText("Showing 11 to 11 of 11 incidents")).toBeTruthy()
  })
})
