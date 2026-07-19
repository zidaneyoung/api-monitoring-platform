import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { MonitorStateButton } from "./monitor-pause-button"
import type { MonitorDto } from "@/lib/monitor-api"


const fetchMock = vi.fn()
const onChanged = vi.fn()
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
  latest_error_category: null,
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock)
  fetchMock.mockReset()
  onChanged.mockReset()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("MonitorStateButton", () => {
  it("cancels without a request and returns focus to the trigger", async () => {
    render(<MonitorStateButton monitor={monitor} onChanged={onChanged} />)
    const trigger = screen.getByRole("button", { name: "Pause monitor" })

    fireEvent.click(trigger)
    const dialog = screen.getByRole("dialog", { name: "Pause Public API?" })
    await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true))
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }))

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
    expect(fetchMock).not.toHaveBeenCalled()
    expect(onChanged).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(trigger)
  })

  it("closes with Escape without submitting", async () => {
    render(<MonitorStateButton monitor={monitor} onChanged={onChanged} />)
    const trigger = screen.getByRole("button", { name: "Pause monitor" })
    fireEvent.click(trigger)
    expect(screen.getByRole("dialog", { name: "Pause Public API?" })).toBeTruthy()

    fireEvent.keyDown(document, { key: "Escape", code: "Escape" })

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
    expect(fetchMock).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(trigger)
  })

  it("pauses once, shows pending text, and announces success", async () => {
    const paused: MonitorDto = { ...monitor, status: "paused", next_check_at: null }
    let finishRequest: (response: Response) => void = () => undefined
    fetchMock.mockReturnValue(new Promise<Response>((resolve) => { finishRequest = resolve }))
    render(<MonitorStateButton monitor={monitor} onChanged={onChanged} />)

    fireEvent.click(screen.getByRole("button", { name: "Pause monitor" }))
    const dialog = screen.getByRole("dialog", { name: "Pause Public API?" })
    const confirm = within(dialog).getByRole("button", { name: "Pause monitor" })
    fireEvent.click(confirm)
    fireEvent.click(confirm)

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(within(dialog).getByRole("button", { name: "Pausing…" }).hasAttribute("disabled")).toBe(true)
    expect(screen.getByRole("button", { name: "Pause monitor", hidden: true }).hasAttribute("disabled")).toBe(true)

    await act(async () => finishRequest(new Response(JSON.stringify(paused), { status: 200 })))
    expect((await screen.findByRole("status")).textContent).toBe("Public API paused.")
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
    expect(onChanged).toHaveBeenCalledWith(paused)
  })

  it("keeps a failed pause unchanged and permits one explicit retry", async () => {
    const paused: MonitorDto = { ...monitor, status: "paused", next_check_at: null }
    fetchMock
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(paused), { status: 200 }))
    render(<MonitorStateButton monitor={monitor} onChanged={onChanged} />)

    fireEvent.click(screen.getByRole("button", { name: "Pause monitor" }))
    const dialog = screen.getByRole("dialog", { name: "Pause Public API?" })
    fireEvent.click(within(dialog).getByRole("button", { name: "Pause monitor" }))

    expect(await within(dialog).findByText("The monitor could not be paused. Try again.")).toBeTruthy()
    expect(onChanged).not.toHaveBeenCalled()
    const retry = within(dialog).getByRole("button", { name: "Pause monitor" })
    expect(retry.hasAttribute("disabled")).toBe(false)

    fireEvent.click(retry)
    await waitFor(() => expect(onChanged).toHaveBeenCalledWith(paused))
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("requires confirmation and uses distinct pending feedback when resuming", async () => {
    const paused: MonitorDto = { ...monitor, status: "paused", next_check_at: null }
    const resumed: MonitorDto = {
      ...monitor,
      status: "unknown",
      next_check_at: "2026-07-16T20:01:00Z",
    }
    let finishRequest: (response: Response) => void = () => undefined
    fetchMock.mockReturnValue(new Promise<Response>((resolve) => { finishRequest = resolve }))
    render(<MonitorStateButton monitor={paused} onChanged={onChanged} />)

    fireEvent.click(screen.getByRole("button", { name: "Resume monitor" }))
    const dialog = screen.getByRole("dialog", { name: "Resume Public API?" })
    expect(fetchMock).not.toHaveBeenCalled()
    fireEvent.click(within(dialog).getByRole("button", { name: "Resume monitor" }))
    expect(within(dialog).getByRole("button", { name: "Resuming…" })).toBeTruthy()

    await act(async () => finishRequest(new Response(JSON.stringify(resumed), { status: 200 })))
    expect((await screen.findByRole("status")).textContent).toBe("Public API resumed.")
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://localhost:8000/monitors/monitor-1/resume")
    expect(onChanged).toHaveBeenCalledWith(resumed)
  })

  it("ignores a state response after its monitor UI is superseded", async () => {
    let finishRequest: (response: Response) => void = () => undefined
    fetchMock.mockReturnValue(new Promise<Response>((resolve) => { finishRequest = resolve }))
    const { unmount } = render(<MonitorStateButton monitor={monitor} onChanged={onChanged} />)

    fireEvent.click(screen.getByRole("button", { name: "Pause monitor" }))
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Pause monitor" }))
    unmount()
    await act(async () => finishRequest(new Response(JSON.stringify({
      ...monitor,
      status: "paused",
      next_check_at: null,
    }), { status: 200 })))

    expect(onChanged).not.toHaveBeenCalled()
  })
})
