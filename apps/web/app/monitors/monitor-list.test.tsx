import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { MonitorList } from "./monitor-list"
import type { MonitorDto, MonitorListDto } from "@/lib/monitor-api"


const fetchMock = vi.fn()
const navigationMock = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }))

vi.mock("next/navigation", () => ({
  useRouter: () => navigationMock,
}))

const unknownMonitor: MonitorDto = {
  id: "monitor-unknown",
  name: "Owner unknown API",
  url: "https://example.com/unknown",
  http_method: "GET",
  interval_seconds: 60,
  timeout_seconds: 10,
  expected_status_min: 200,
  expected_status_max: 399,
  failure_threshold: 3,
  recovery_threshold: 2,
  status: "unknown",
  next_check_at: "2026-07-16T18:00:00Z",
  last_checked_at: null,
  latest_response_time_ms: null,
  latest_status_code: null,
  latest_error_category: null,
}

const pausedMonitor: MonitorDto = {
  ...unknownMonitor,
  id: "monitor-paused",
  name: "Owner paused API",
  status: "paused",
  last_checked_at: "2026-07-16T17:00:00Z",
  latest_response_time_ms: 125,
  latest_status_code: 204,
}

function responsePage(overrides: Partial<MonitorListDto> = {}): Response {
  return new Response(JSON.stringify({
    items: [unknownMonitor, pausedMonitor],
    page: 1,
    page_size: 10,
    total: 2,
    pages: 1,
    ...overrides,
  }), { status: 200 })
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock)
  fetchMock.mockReset()
  navigationMock.push.mockReset()
  navigationMock.replace.mockReset()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("MonitorList", () => {
  it("renders backend-owned monitors including unknown and paused states", async () => {
    fetchMock.mockResolvedValue(responsePage())
    render(<MonitorList />)

    expect(screen.getByText("Loading monitors")).toBeTruthy()
    expect((await screen.findAllByText("Owner unknown API")).length).toBeGreaterThan(0)
    expect(screen.getAllByText("Owner paused API").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Unknown").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Paused").length).toBeGreaterThan(0)
    expect(screen.getAllByText("125 ms").length).toBeGreaterThan(0)
    expect(screen.getAllByText("204").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Not checked yet").length).toBeGreaterThan(0)
    expect(screen.getAllByTitle("UTC: 2026-07-16T17:00:00Z").length).toBeGreaterThan(0)
    expect(screen.queryByText("Checkout")).toBeNull()
    fireEvent.click(screen.getAllByRole("button", { name: "Actions for Owner unknown API" })[0])
    expect((await screen.findByRole("link", { name: "Edit monitor" })).getAttribute("href")).toBe("/monitors/monitor-unknown/edit?return_to=%2Fmonitors%3Fpage%3D1%26page_size%3D10")
  })

  it("renders the backend empty state", async () => {
    fetchMock.mockResolvedValue(responsePage({ items: [], total: 0 }))
    render(<MonitorList />)
    expect(await screen.findByText("No monitors yet")).toBeTruthy()
  })

  it("renders a safe normalized error when no response values exist", async () => {
    fetchMock.mockResolvedValue(responsePage({
      items: [{
        ...unknownMonitor,
        name: "Failed API",
        last_checked_at: "2026-07-18T12:30:00Z",
        latest_error_category: "connection",
      }],
      total: 1,
    }))
    render(<MonitorList />)

    expect((await screen.findAllByText("Failed API")).length).toBeGreaterThan(0)
    expect(screen.getAllByText("Connection failure").length).toBeGreaterThan(0)
  })

  it("renders a controlled error and retries", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(null, { status: 500 }))
      .mockResolvedValueOnce(responsePage({ items: [], total: 0 }))
    render(<MonitorList />)

    fireEvent.click(await screen.findByRole("button", { name: "Try again" }))
    expect(await screen.findByText("No monitors yet")).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("requests the next backend page", async () => {
    fetchMock
      .mockResolvedValueOnce(responsePage({ items: [unknownMonitor], total: 2, pages: 2 }))
      .mockResolvedValueOnce(responsePage({ items: [pausedMonitor], page: 2, total: 2, pages: 2 }))
    render(<MonitorList />)

    expect((await screen.findAllByText("Owner unknown API")).length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole("button", { name: "Next page" }))
    expect((await screen.findAllByText("Owner paused API")).length).toBeGreaterThan(0)
    expect(navigationMock.push).toHaveBeenCalledWith("/monitors?page=2&page_size=10", { scroll: false })
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://localhost:8000/monitors?page=2&page_size=10")
  })

  it("loads pagination from the URL-backed page inputs and preserves it in detail links", async () => {
    fetchMock.mockResolvedValue(responsePage({ items: [pausedMonitor], page: 2, page_size: 25, total: 30, pages: 2 }))
    render(<MonitorList initialPage={2} initialPageSize={25} />)

    const details = (await screen.findAllByRole("link", { name: "Owner paused API" }))[0]
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://localhost:8000/monitors?page=2&page_size=25")
    expect(details.getAttribute("href")).toBe("/monitors/monitor-paused?return_to=%2Fmonitors%3Fpage%3D2%26page_size%3D25")
  })

  it("ignores a superseded page response that finishes last", async () => {
    let finishFirst: (response: Response) => void = () => undefined
    let finishSecond: (response: Response) => void = () => undefined
    fetchMock
      .mockReturnValueOnce(new Promise<Response>((resolve) => { finishFirst = resolve }))
      .mockReturnValueOnce(new Promise<Response>((resolve) => { finishSecond = resolve }))
    const { rerender } = render(<MonitorList initialPage={1} initialPageSize={10} />)

    rerender(<MonitorList initialPage={2} initialPageSize={10} />)
    await act(async () => finishSecond(responsePage({ items: [pausedMonitor], page: 2, total: 2, pages: 2 })))
    expect((await screen.findAllByText("Owner paused API")).length).toBeGreaterThan(0)

    await act(async () => finishFirst(responsePage({ items: [unknownMonitor], page: 1, total: 2, pages: 2 })))
    expect(screen.queryByText("Owner unknown API")).toBeNull()
    expect(screen.getAllByText("Owner paused API").length).toBeGreaterThan(0)
  })

  it("renders an invalid backend timestamp safely without changing its source", async () => {
    fetchMock.mockResolvedValue(responsePage({ items: [{ ...pausedMonitor, last_checked_at: "not-a-timestamp" }], total: 1 }))
    render(<MonitorList />)

    expect((await screen.findAllByText("Unavailable")).length).toBeGreaterThan(0)
    expect(screen.getAllByTitle("Received value: not-a-timestamp").length).toBeGreaterThan(0)
  })

  it("confirms deletion and removes the monitor from the active list", async () => {
    fetchMock
      .mockResolvedValueOnce(responsePage({ items: [unknownMonitor], total: 1 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    render(<MonitorList />)

    expect((await screen.findAllByText("Owner unknown API")).length).toBeGreaterThan(0)
    fireEvent.click(screen.getAllByRole("button", { name: "Actions for Owner unknown API" })[0])
    fireEvent.click(await screen.findByRole("button", { name: "Delete monitor" }))
    fireEvent.click(within(screen.getByRole("dialog", { name: "Permanently delete Owner unknown API?" })).getByRole("button", { name: "Delete permanently" }))
    expect(await screen.findByText("No monitors yet")).toBeTruthy()
    expect(screen.queryByText("Owner unknown API")).toBeNull()
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://localhost:8000/monitors/monitor-unknown")
  })

  it("returns to the previous URL page after deleting its final row", async () => {
    fetchMock
      .mockResolvedValueOnce(responsePage({ items: [pausedMonitor], page: 2, page_size: 5, total: 6, pages: 2 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(responsePage({ items: [unknownMonitor], page: 1, page_size: 5, total: 5, pages: 1 }))
    render(<MonitorList initialPage={2} initialPageSize={5} />)

    expect((await screen.findAllByText("Owner paused API")).length).toBeGreaterThan(0)
    fireEvent.click(screen.getAllByRole("button", { name: "Actions for Owner paused API" })[0])
    fireEvent.click(await screen.findByRole("button", { name: "Delete monitor" }))
    fireEvent.click(within(screen.getByRole("dialog", { name: "Permanently delete Owner paused API?" })).getByRole("button", { name: "Delete permanently" }))

    expect((await screen.findAllByText("Owner unknown API")).length).toBeGreaterThan(0)
    expect(navigationMock.replace).toHaveBeenCalledWith("/monitors?page=1&page_size=5", { scroll: false })
    expect(fetchMock.mock.calls[2]?.[0]).toBe("http://localhost:8000/monitors?page=1&page_size=5")
  })
})
