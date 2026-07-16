import { describe, expect, it } from "vitest"

import {
  monitorDetailsHref,
  monitorEditHref,
  monitorListHref,
  parseMonitorListSearch,
  safeMonitorReturnHref,
} from "./monitor-navigation"


describe("monitor navigation", () => {
  it("parses supported pagination values", () => {
    expect(parseMonitorListSearch({ page: "3", page_size: "25" })).toEqual({ page: 3, pageSize: 25 })
    expect(monitorListHref(3, 25)).toBe("/monitors?page=3&page_size=25")
  })

  it("falls back safely for invalid pagination values", () => {
    expect(parseMonitorListSearch({ page: "-2", page_size: "100" })).toEqual({ page: 1, pageSize: 10 })
    expect(parseMonitorListSearch({ page: "1.5", page_size: ["5", "25"] })).toEqual({ page: 1, pageSize: 5 })
  })

  it("accepts only canonical monitor-list return destinations", () => {
    expect(safeMonitorReturnHref("/monitors?page=4&page_size=5")).toBe("/monitors?page=4&page_size=5")
    expect(safeMonitorReturnHref("/monitors?page=bad&page_size=25")).toBe("/monitors?page=1&page_size=25")
    expect(safeMonitorReturnHref("https://evil.example/monitors?page=4&page_size=5")).toBe("/monitors?page=1&page_size=10")
    expect(safeMonitorReturnHref("/dashboard")).toBe("/monitors?page=1&page_size=10")
  })

  it("propagates the list return URL through details and edit", () => {
    const returnHref = "/monitors?page=2&page_size=25"
    expect(monitorDetailsHref("monitor one", returnHref)).toBe("/monitors/monitor%20one?return_to=%2Fmonitors%3Fpage%3D2%26page_size%3D25")
    expect(monitorEditHref("monitor one", returnHref)).toBe("/monitors/monitor%20one/edit?return_to=%2Fmonitors%3Fpage%3D2%26page_size%3D25")
  })
})
