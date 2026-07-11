import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { readFileSync } from "node:fs"
import { afterEach, describe, expect, it, vi } from "vitest"

import { EmptyState } from "./empty-state"
import { ErrorState } from "./error-state"
import { LoadingState } from "./loading"

afterEach(cleanup)

describe("asynchronous states", () => {
  it("announces loading and renders skeleton content distinct from empty content", () => {
    const { container } = render(<LoadingState label="Loading monitors" count={3} />)

    expect(screen.getByRole("status").getAttribute("aria-busy")).toBe("true")
    expect(screen.getByText("Loading monitors").classList.contains("sr-only")).toBe(true)
    expect(container.querySelectorAll("[data-slot='card'][aria-hidden='true']")).toHaveLength(3)
    expect(screen.queryByText(/no monitors/i)).toBeNull()
  })

  it("explains empty content and exposes its action", () => {
    render(
      <EmptyState
        title="No monitors yet"
        description="No endpoints are being checked. Create a monitor to begin."
        action={<button type="button">Create monitor</button>}
      />
    )

    expect(screen.getByRole("status", { name: "No monitors yet" })).toBeTruthy()
    expect(screen.getByText(/no endpoints are being checked/i)).toBeTruthy()
    expect(screen.getByRole("button", { name: "Create monitor" }).hasAttribute("disabled")).toBe(false)
  })

  it("announces load failure and provides a working retry action", () => {
    const retry = vi.fn()
    render(
      <ErrorState
        title="Unable to load monitors"
        description="Monitor data could not be loaded. Retry the request."
        action={<button type="button" onClick={retry}>Try again</button>}
      />
    )

    expect(screen.getByRole("alert", { name: "Unable to load monitors" })).toBeTruthy()
    expect(screen.getByText(/could not be loaded/i)).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Try again" }))
    expect(retry).toHaveBeenCalledTimes(1)
  })

  it("uses theme tokens instead of fixed light or dark colors", () => {
    const css = readFileSync("app/globals.css", "utf8")
    const lightTheme = css.slice(css.indexOf(":root {"), css.indexOf(".dark {"))
    const darkTheme = css.slice(css.indexOf(".dark {"), css.indexOf("@layer base"))
    const { rerender } = render(<EmptyState title="Empty" description="Nothing exists yet." />)
    expect(screen.getByRole("status").classList.contains("border-dashed")).toBe(true)
    expect(lightTheme).toContain("--muted:")
    expect(lightTheme).toContain("--destructive:")

    rerender(<ErrorState title="Failed" description="Loading failed." />)
    expect(screen.getByRole("alert").classList.contains("bg-destructive/5")).toBe(true)
    expect(darkTheme).toContain("--muted:")
    expect(darkTheme).toContain("--destructive:")
  })
})
