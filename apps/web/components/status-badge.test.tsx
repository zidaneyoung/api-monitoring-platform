import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { StatusBadge } from "./status-badge"


afterEach(cleanup)

describe("StatusBadge", () => {
  it("uses text and a distinct icon for every monitor state", () => {
    const { container, rerender } = render(<StatusBadge status="unknown" />)
    const unknownIcon = container.querySelector("svg")?.getAttribute("class")
    expect(screen.getByText("Unknown")).toBeTruthy()

    rerender(<StatusBadge status="paused" />)
    const pausedIcon = container.querySelector("svg")?.getAttribute("class")
    expect(screen.getByText("Paused")).toBeTruthy()

    rerender(<StatusBadge status="up" />)
    const upIcon = container.querySelector("svg")?.getAttribute("class")
    expect(screen.getByText("Up")).toBeTruthy()

    rerender(<StatusBadge status="down" />)
    const downIcon = container.querySelector("svg")?.getAttribute("class")
    expect(screen.getByText("Down")).toBeTruthy()
    expect(new Set([unknownIcon, pausedIcon, upIcon, downIcon]).size).toBe(4)
  })
})
