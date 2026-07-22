import { describe, expect, it } from "vitest"

import { readApiError } from "@/lib/api-error"


describe("readApiError", () => {
  it("parses the documented field and retry structure", async () => {
    const response = new Response(JSON.stringify({
      error: {
        code: "validation_error",
        message: "Request validation failed.",
        fields: [{ field: "email", message: "Enter a valid email address." }],
        retry_after_seconds: 17.2,
      },
    }), { status: 422 })

    await expect(readApiError(response)).resolves.toEqual({
      code: "validation_error",
      message: "Request validation failed.",
      fields: [{ field: "email", message: "Enter a valid email address." }],
      retryAfterSeconds: 18,
    })
  })

  it.each([
    new Response("not json", { status: 500 }),
    new Response(JSON.stringify({ detail: "legacy response" }), { status: 500 }),
    new Response(JSON.stringify({ error: { code: 500, message: null } }), { status: 500 }),
  ])("handles malformed or unexpected responses safely", async (response) => {
    await expect(readApiError(response)).resolves.toBeNull()
  })

  it("ignores malformed field entries and bounds retry data", async () => {
    const response = new Response(JSON.stringify({
      error: {
        code: "rate_limited",
        message: "Try again later.",
        fields: [null, { field: "form" }, { field: "form", message: "Retry later." }],
        retry_after_seconds: 999_999,
      },
    }), { status: 429 })

    await expect(readApiError(response)).resolves.toEqual({
      code: "rate_limited",
      message: "Try again later.",
      fields: [{ field: "form", message: "Retry later." }],
      retryAfterSeconds: 86_400,
    })
  })
})
