import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { listRecentChecks, type MonitorCheckListDto } from "@/lib/monitor-api"
import { RecentChecks } from "./recent-checks"

vi.mock("@/lib/monitor-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/monitor-api")>()
  return { ...actual, listRecentChecks: vi.fn() }
})

function page(overrides: Partial<MonitorCheckListDto> = {}): MonitorCheckListDto {
  return {
    items: [
      { id: "newest", success: true, completed_at: "2026-07-18T14:03:00Z", response_time_ms: 103, http_status_code: 203, error_category: null },
      { id: "failed", success: false, completed_at: "2026-07-18T14:02:00Z", response_time_ms: null, http_status_code: null, error_category: "connection" },
    ],
    page: 1,
    page_size: 5,
    total: 3,
    pages: 2,
    ...overrides,
  }
}

afterEach(() => {
  cleanup()
  vi.mocked(listRecentChecks).mockReset()
})

describe("RecentChecks", () => {
  it("renders newest-first success, failure, null values, safe errors, and pagination", async () => {
    vi.mocked(listRecentChecks).mockImplementation(async (_monitorId, requestedPage) => ({
      type: "success",
      data: requestedPage === 1
        ? page()
        : page({
          items: [{ id: "oldest", success: true, completed_at: "2026-07-18T14:01:00Z", response_time_ms: 101, http_status_code: 201, error_category: null }],
          page: 2,
        }),
    }))
    const { container } = render(<RecentChecks monitorId="monitor-1" />)

    expect(screen.getByText("Loading recent checks")).toBeTruthy()
    expect(await screen.findByText("Success")).toBeTruthy()
    const articles = container.querySelectorAll("article")
    expect(articles).toHaveLength(2)
    expect(within(articles[0]).getByText("103 ms")).toBeTruthy()
    expect(within(articles[1]).getByText("Failure")).toBeTruthy()
    expect(within(articles[1]).getAllByText("—")).toHaveLength(2)
    expect(within(articles[1]).getByText("Connection failure")).toBeTruthy()
    expect(screen.getByTitle("UTC: 2026-07-18T14:03:00Z")).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    expect(await screen.findByText("101 ms")).toBeTruthy()
    expect(listRecentChecks).toHaveBeenLastCalledWith("monitor-1", 2, 5, { signal: expect.any(AbortSignal) })
  })

  it("renders a clear empty state", async () => {
    vi.mocked(listRecentChecks).mockResolvedValue({
      type: "success",
      data: page({ items: [], total: 0, pages: 1 }),
    })
    render(<RecentChecks monitorId="monitor-1" />)

    expect(await screen.findByRole("status", { name: "No completed checks" })).toBeTruthy()
  })

  it("renders a controlled error and retries", async () => {
    vi.mocked(listRecentChecks)
      .mockResolvedValueOnce({ type: "unavailable" })
      .mockResolvedValueOnce({ type: "success", data: page() })
    render(<RecentChecks monitorId="monitor-1" />)

    fireEvent.click(await screen.findByRole("button", { name: "Try again" }))
    await waitFor(() => expect(listRecentChecks).toHaveBeenCalledTimes(2))
    expect(await screen.findByText("Recent checks")).toBeTruthy()
  })
})
