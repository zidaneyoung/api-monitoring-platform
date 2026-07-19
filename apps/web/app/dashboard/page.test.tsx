import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import DashboardPage from "./page"

vi.mock("./monitor-summary", () => ({
  MonitorSummary: () => <section>Live monitor summary</section>,
}))

vi.mock("./recent-monitors", () => ({
  RecentMonitors: () => <section>Live recent monitors</section>,
}))

vi.mock("./active-incidents", () => ({
  ActiveIncidents: () => <section>Live active incidents</section>,
}))

afterEach(cleanup)

describe("DashboardPage", () => {
  it("renders only API-backed dashboard sections without demo data", () => {
    render(<DashboardPage />)

    expect(screen.getByText("Live monitor summary")).toBeTruthy()
    expect(screen.getByText("Live recent monitors")).toBeTruthy()
    expect(screen.getByText("Live active incidents")).toBeTruthy()
    expect(screen.queryByText(/Placeholder overview/i)).toBeNull()
    expect(screen.queryByText(/Median 184 ms/i)).toBeNull()
    expect(screen.queryByText(/Loading dashboard/i)).toBeNull()
  })
})
