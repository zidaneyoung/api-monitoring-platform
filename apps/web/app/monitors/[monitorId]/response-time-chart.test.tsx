import type { ReactNode } from "react"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { getMonitorResponseTimes, type MonitorResponseTimeSeriesDto } from "@/lib/monitor-api"
import { ResponseTimeChart } from "./response-time-chart"

vi.mock("@/lib/monitor-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/monitor-api")>()
  return { ...actual, getMonitorResponseTimes: vi.fn() }
})

vi.mock("recharts", () => ({
  CartesianGrid: () => null,
  Line: ({ connectNulls }: { connectNulls: boolean }) => <div data-testid="response-line" data-connect-nulls={String(connectNulls)} />,
  LineChart: ({ accessibilityLayer, children, data }: { accessibilityLayer?: boolean; children: ReactNode; data: unknown[] }) => (
    <div data-testid="line-chart" data-accessible={String(accessibilityLayer)} data-series={JSON.stringify(data)}>{children}</div>
  ),
  ResponsiveContainer: ({ children, height, width }: { children: ReactNode; height: string; width: string }) => (
    <div data-testid="responsive-container" data-height={height} data-width={width}>{children}</div>
  ),
  Tooltip: () => null,
  XAxis: ({ dataKey }: { dataKey: string }) => <div data-testid="x-axis" data-key={dataKey} />,
  YAxis: ({ label, unit }: { label: { value: string }; unit: string }) => <div data-testid="y-axis" data-label={label.value} data-unit={unit} />,
}))

function series(points: MonitorResponseTimeSeriesDto["points"]): MonitorResponseTimeSeriesDto {
  return {
    range: "24h",
    started_at: "2026-07-18T15:00:00Z",
    ended_at: "2026-07-19T15:00:00Z",
    points,
  }
}

afterEach(() => {
  cleanup()
  vi.mocked(getMonitorResponseTimes).mockReset()
})

describe("ResponseTimeChart", () => {
  it("plots persisted points chronologically with time, milliseconds, null gaps, and a responsive accessible container", async () => {
    vi.mocked(getMonitorResponseTimes).mockResolvedValue({
      type: "success",
      data: series([
        { completed_at: "2026-07-19T14:00:00Z", response_time_ms: 95, success: true },
        { completed_at: "2026-07-19T12:00:00Z", response_time_ms: 120, success: true },
        { completed_at: "2026-07-19T13:00:00Z", response_time_ms: null, success: false },
      ]),
    })
    render(<ResponseTimeChart monitorId="monitor-1" />)

    expect(await screen.findByText(/Last 24 hours/)).toBeTruthy()
    expect(screen.getByRole("img", { name: /Response time in milliseconds over the last 24 hours/ })).toBeTruthy()
    expect(screen.getByTestId("responsive-container").getAttribute("data-width")).toBe("100%")
    expect(screen.getByTestId("line-chart").getAttribute("data-accessible")).toBe("true")
    expect(screen.getByTestId("x-axis").getAttribute("data-key")).toBe("completed_at")
    expect(screen.getByTestId("y-axis").getAttribute("data-unit")).toBe(" ms")
    expect(screen.getByTestId("y-axis").getAttribute("data-label")).toBe("Milliseconds")
    expect(screen.getByTestId("response-line").getAttribute("data-connect-nulls")).toBe("false")
    const plotted = JSON.parse(screen.getByTestId("line-chart").getAttribute("data-series") ?? "[]")
    expect(plotted.map((point: { response_time_ms: number | null }) => point.response_time_ms)).toEqual([120, null, 95])
  })

  it("shows an empty state when no measured points exist", async () => {
    vi.mocked(getMonitorResponseTimes).mockResolvedValue({
      type: "success",
      data: series([{ completed_at: "2026-07-19T13:00:00Z", response_time_ms: null, success: false }]),
    })
    render(<ResponseTimeChart monitorId="monitor-1" />)

    expect(await screen.findByRole("status", { name: "No response-time data" })).toBeTruthy()
  })

  it("shows a controlled error and retries", async () => {
    vi.mocked(getMonitorResponseTimes)
      .mockResolvedValueOnce({ type: "unavailable" })
      .mockResolvedValueOnce({ type: "success", data: series([{ completed_at: "2026-07-19T14:00:00Z", response_time_ms: 95, success: true }]) })
    render(<ResponseTimeChart monitorId="monitor-1" />)

    fireEvent.click(await screen.findByRole("button", { name: "Try again" }))
    await waitFor(() => expect(getMonitorResponseTimes).toHaveBeenCalledTimes(2))
    expect(await screen.findByText("Response time")).toBeTruthy()
  })
})
