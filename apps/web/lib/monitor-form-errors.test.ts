import { describe, expect, it } from "vitest"

import type { MonitorCreatePayload, MonitorOutcome } from "@/lib/monitor-api"
import { adaptMonitorFormFailure, validateMonitorPayload } from "@/lib/monitor-form-errors"


const validPayload: MonitorCreatePayload = {
  name: "Public API",
  url: "https://example.com/health",
  http_method: "GET",
  interval_seconds: 60,
  timeout_seconds: 10,
  expected_status_min: 200,
  expected_status_max: 399,
  failure_threshold: 3,
  recovery_threshold: 2,
}

describe("adaptMonitorFormFailure", () => {
  it("separates backend field errors from general errors", () => {
    const outcome: MonitorOutcome<never> = {
      type: "validation",
      errors: [
        { field: "url", message: "Enter a valid URL." },
        { field: "form", message: "Review the request." },
      ],
    }

    expect(adaptMonitorFormFailure(outcome, "create")).toEqual({
      category: "validation",
      fieldErrors: [{ field: "url", message: "Enter a valid URL." }],
      generalErrors: ["Review the request."],
    })
  })

  it.each([
    ["unauthenticated", "authentication"],
    ["forbidden", "authorization"],
    ["not_found", "not_found"],
    ["conflict", "conflict"],
    ["rate_limited", "rate_limit"],
    ["internal_error", "internal_error"],
    ["unexpected_response", "unknown"],
  ] as const)("maps %s to the %s category", (type, category) => {
    expect(adaptMonitorFormFailure({ type }, "edit")).toMatchObject({
      category,
      fieldErrors: [],
    })
  })
})

describe("validateMonitorPayload", () => {
  it("accepts a browser-safe monitor configuration", () => {
    expect(validateMonitorPayload(validPayload)).toBeNull()
  })

  it("checks required values, basic URL syntax, numeric ranges, and status order", () => {
    const errors = validateMonitorPayload({
      ...validPayload,
      name: " ",
      url: "ftp://example.com/health",
      interval_seconds: 0,
      timeout_seconds: 301,
      expected_status_min: 500,
      expected_status_max: 400,
      failure_threshold: 1.5,
      recovery_threshold: 101,
    })

    expect(errors?.fieldErrors.map((error) => error.field)).toEqual([
      "name",
      "url",
      "interval_seconds",
      "timeout_seconds",
      "failure_threshold",
      "recovery_threshold",
      "expected_status_min",
      "expected_status_max",
    ])
  })
})
