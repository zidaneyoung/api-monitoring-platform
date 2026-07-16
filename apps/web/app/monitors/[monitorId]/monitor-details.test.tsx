import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { MonitorDetails } from "./monitor-details"
import type { MonitorDto } from "@/lib/monitor-api"


const fetchMock = vi.fn()
const navigationMock = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }))
const returnHref = "/monitors?page=3&page_size=25"

vi.mock("next/navigation", () => ({
  useRouter: () => navigationMock,
}))

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
  navigationMock.push.mockReset()
  navigationMock.refresh.mockReset()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("MonitorDetails", () => {
  it("renders backend-authoritative configuration and latest state", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify(monitor), { status: 200 }))
    render(<MonitorDetails monitorId={monitor.id} returnHref={returnHref} />)

    expect(screen.getByText("Loading monitor details")).toBeTruthy()
    expect(await screen.findByText("Owned details API")).toBeTruthy()
    expect(screen.getAllByText("Up").length).toBeGreaterThan(0)
    expect(screen.getByText("HEAD")).toBeTruthy()
    expect(screen.getByText("5 minutes")).toBeTruthy()
    expect(screen.getByText("200–399")).toBeTruthy()
    expect(screen.getByText("Current state")).toBeTruthy()
    expect(screen.getByText("Endpoint configuration")).toBeTruthy()
    expect(screen.getByText("Schedule configuration")).toBeTruthy()
    expect(screen.getByText("Success criteria")).toBeTruthy()
    expect(screen.getByText("Available actions")).toBeTruthy()
    expect(screen.queryByText("125 ms")).toBeNull()
    expect(screen.queryByText("No check history loaded.")).toBeNull()
    expect(screen.getByRole("link", { name: "Edit monitor" }).getAttribute("href")).toBe("/monitors/monitor-owned/edit?return_to=%2Fmonitors%3Fpage%3D3%26page_size%3D25")
    expect(screen.getByRole("link", { name: "Back to monitors" }).getAttribute("href")).toBe(returnHref)
    expect(screen.getByRole("link", { name: "Open endpoint" }).getAttribute("target")).toBe("_blank")
    expect(screen.getByRole("link", { name: "Open endpoint" }).getAttribute("rel")).toBe("noopener noreferrer")
    expect(screen.queryByText(/mock/i)).toBeNull()
  })

  it("shows visible endpoint copy success", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal("navigator", { clipboard: { writeText } })
    fetchMock.mockResolvedValue(new Response(JSON.stringify(monitor), { status: 200 }))
    render(<MonitorDetails monitorId={monitor.id} returnHref={returnHref} />)

    fireEvent.click(await screen.findByRole("button", { name: "Copy endpoint" }))
    expect((await screen.findByRole("status")).textContent).toBe("Endpoint URL copied.")
    expect(writeText).toHaveBeenCalledWith(monitor.url)
  })

  it("shows a visible endpoint copy failure", async () => {
    vi.stubGlobal("navigator", { clipboard: { writeText: vi.fn().mockRejectedValue(new Error("denied")) } })
    fetchMock.mockResolvedValue(new Response(JSON.stringify(monitor), { status: 200 }))
    render(<MonitorDetails monitorId={monitor.id} returnHref={returnHref} />)

    fireEvent.click(await screen.findByRole("button", { name: "Copy endpoint" }))
    expect((await screen.findByRole("alert")).textContent).toContain("could not be copied")
  })

  it("renders the ownership-safe missing state", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 404 }))
    render(<MonitorDetails monitorId="missing-monitor" returnHref={returnHref} />)

    expect(await screen.findByText("Monitor not found")).toBeTruthy()
    expect(screen.getByText("This monitor does not exist or is not available to your account.")).toBeTruthy()
  })

  it("renders a controlled error and retries", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(null, { status: 500 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(monitor), { status: 200 }))
    render(<MonitorDetails monitorId={monitor.id} returnHref={returnHref} />)

    fireEvent.click(await screen.findByRole("button", { name: "Try again" }))
    expect(await screen.findByText("Owned details API")).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("ignores a superseded detail response that finishes last", async () => {
    let finishFirst: (response: Response) => void = () => undefined
    let finishSecond: (response: Response) => void = () => undefined
    fetchMock
      .mockReturnValueOnce(new Promise<Response>((resolve) => { finishFirst = resolve }))
      .mockReturnValueOnce(new Promise<Response>((resolve) => { finishSecond = resolve }))
    const { rerender } = render(<MonitorDetails monitorId="monitor-old" returnHref={returnHref} />)

    rerender(<MonitorDetails monitorId="monitor-new" returnHref={returnHref} />)
    await act(async () => finishSecond(new Response(JSON.stringify({ ...monitor, id: "monitor-new", name: "New monitor" }), { status: 200 })))
    expect(await screen.findByText("New monitor")).toBeTruthy()

    await act(async () => finishFirst(new Response(JSON.stringify({ ...monitor, id: "monitor-old", name: "Old monitor" }), { status: 200 })))
    expect(screen.queryByText("Old monitor")).toBeNull()
    expect(screen.getByText("New monitor")).toBeTruthy()
  })

  it("confirms pause and immediately renders the persisted paused state", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify(monitor), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ...monitor,
        status: "paused",
        next_check_at: null,
      }), { status: 200 }))
    render(<MonitorDetails monitorId={monitor.id} returnHref={returnHref} />)

    fireEvent.click(await screen.findByRole("button", { name: "Pause monitor" }))
    fireEvent.click(within(screen.getByRole("dialog", { name: "Pause Owned details API?" })).getByRole("button", { name: "Pause monitor" }))
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
    render(<MonitorDetails monitorId={monitor.id} returnHref={returnHref} />)

    fireEvent.click(await screen.findByRole("button", { name: "Resume monitor" }))
    fireEvent.click(within(screen.getByRole("dialog", { name: "Resume Owned details API?" })).getByRole("button", { name: "Resume monitor" }))
    expect(await screen.findByRole("button", { name: "Pause monitor" })).toBeTruthy()
    expect(screen.getAllByText("Unknown").length).toBeGreaterThan(0)
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://localhost:8000/monitors/monitor-owned/resume")
  })

  it("confirms permanent deletion and returns to the active list", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify(monitor), { status: 200 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    render(<MonitorDetails monitorId={monitor.id} returnHref={returnHref} />)

    fireEvent.click(await screen.findByRole("button", { name: "Delete monitor" }))
    fireEvent.click(within(screen.getByRole("dialog", { name: "Permanently delete Owned details API?" })).getByRole("button", { name: "Delete permanently" }))
    await waitFor(() => expect(navigationMock.push).toHaveBeenCalledWith(returnHref))
    expect(navigationMock.refresh).toHaveBeenCalledOnce()
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://localhost:8000/monitors/monitor-owned")
  })

  it("prevents a conflicting delete while a pause request is pending", async () => {
    let finishPause: (response: Response) => void = () => undefined
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify(monitor), { status: 200 }))
      .mockReturnValueOnce(new Promise<Response>((resolve) => { finishPause = resolve }))
    render(<MonitorDetails monitorId={monitor.id} returnHref={returnHref} />)

    fireEvent.click(await screen.findByRole("button", { name: "Pause monitor" }))
    fireEvent.click(within(screen.getByRole("dialog", { name: "Pause Owned details API?" })).getByRole("button", { name: "Pause monitor" }))

    expect(screen.getByRole("button", { name: "Delete monitor", hidden: true }).hasAttribute("disabled")).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(2)

    await act(async () => finishPause(new Response(JSON.stringify({
      ...monitor,
      status: "paused",
      next_check_at: null,
    }), { status: 200 })))
    expect(await screen.findByRole("button", { name: "Resume monitor" })).toBeTruthy()
  })
})
