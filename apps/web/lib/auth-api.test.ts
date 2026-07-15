import { describe, expect, it } from "vitest"

import { safeAuthRedirect } from "@/lib/auth-api"


describe("safeAuthRedirect", () => {
  it.each([
    [undefined, "/dashboard"],
    ["https://attacker.example/path", "/dashboard"],
    ["//attacker.example/path", "/dashboard"],
    ["/\\attacker.example/path", "/dashboard"],
    ["/monitors/123?tab=checks", "/monitors/123?tab=checks"],
  ])("maps %s to %s", (destination, expected) => {
    expect(safeAuthRedirect(destination)).toBe(expected)
  })
})
