import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { MonitorDeleteButton } from "./monitor-delete-button"
import type { MonitorDto } from "@/lib/monitor-api"


const fetchMock = vi.fn()
const onDeleted = vi.fn()
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
  onDeleted.mockReset()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("MonitorDeleteButton", () => {
  it("cancels without deleting and returns focus to the trigger", async () => {
    render(<MonitorDeleteButton monitor={monitor} onDeleted={onDeleted} />)
    const trigger = screen.getByRole("button", { name: "Delete monitor" })

    fireEvent.click(trigger)
    const dialog = screen.getByRole("dialog", { name: "Permanently delete Public API?" })
    expect(within(dialog).getByText(/related checks and incident history/)).toBeTruthy()
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }))

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
    expect(fetchMock).not.toHaveBeenCalled()
    expect(onDeleted).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(trigger)
  })

  it("closes with Escape without deleting", async () => {
    render(<MonitorDeleteButton monitor={monitor} onDeleted={onDeleted} />)
    fireEvent.click(screen.getByRole("button", { name: "Delete monitor" }))
    expect(screen.getByRole("dialog", { name: "Permanently delete Public API?" })).toBeTruthy()

    fireEvent.keyDown(document, { key: "Escape", code: "Escape" })

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("deletes once, shows pending text, announces success, then completes", async () => {
    let finishRequest: (response: Response) => void = () => undefined
    fetchMock.mockReturnValue(new Promise<Response>((resolve) => { finishRequest = resolve }))
    render(<MonitorDeleteButton monitor={monitor} onDeleted={onDeleted} />)

    fireEvent.click(screen.getByRole("button", { name: "Delete monitor" }))
    const dialog = screen.getByRole("dialog", { name: "Permanently delete Public API?" })
    const confirm = within(dialog).getByRole("button", { name: "Delete permanently" })
    fireEvent.click(confirm)
    fireEvent.click(confirm)

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(within(dialog).getByRole("button", { name: "Deleting…" }).hasAttribute("disabled")).toBe(true)
    expect(screen.getByRole("button", { name: "Delete monitor", hidden: true }).hasAttribute("disabled")).toBe(true)

    await act(async () => finishRequest(new Response(null, { status: 204 })))
    expect((await screen.findByRole("status")).textContent).toBe("Public API deleted.")
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
    expect(onDeleted).not.toHaveBeenCalled()
    await waitFor(() => expect(onDeleted).toHaveBeenCalledWith("monitor-1"))
  })

  it("keeps a failed deletion visible and explicitly retryable", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 503 }))
    render(<MonitorDeleteButton monitor={monitor} onDeleted={onDeleted} />)

    fireEvent.click(screen.getByRole("button", { name: "Delete monitor" }))
    const dialog = screen.getByRole("dialog", { name: "Permanently delete Public API?" })
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete permanently" }))

    expect(await within(dialog).findByText("The monitor could not be deleted. Try again.")).toBeTruthy()
    expect(onDeleted).not.toHaveBeenCalled()
    expect(within(dialog).getByRole("button", { name: "Delete permanently" }).hasAttribute("disabled")).toBe(false)
    expect(screen.getByRole("button", { name: "Delete monitor", hidden: true }).hasAttribute("disabled")).toBe(false)
  })

  it("ignores a delete response after its monitor UI is superseded", async () => {
    let finishRequest: (response: Response) => void = () => undefined
    fetchMock.mockReturnValue(new Promise<Response>((resolve) => { finishRequest = resolve }))
    const { unmount } = render(<MonitorDeleteButton monitor={monitor} onDeleted={onDeleted} />)

    fireEvent.click(screen.getByRole("button", { name: "Delete monitor" }))
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete permanently" }))
    unmount()
    await act(async () => finishRequest(new Response(null, { status: 204 })))

    expect(onDeleted).not.toHaveBeenCalled()
  })
})
