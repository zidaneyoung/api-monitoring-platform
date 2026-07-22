import { expect, test, type Page } from "@playwright/test"


const API_BASE_URL = process.env.E2E_API_BASE_URL ?? "http://127.0.0.1:8800"
const TARGET_CONTROL_URL = process.env.E2E_TARGET_CONTROL_URL ?? "http://127.0.0.1:8801"
const PASSWORD = "E2e-password-123!"

type Monitor = {
  id: string
  name: string
  status: "unknown" | "up" | "down" | "paused"
}

type MonitorList = {
  items: Monitor[]
  total: number
}

type MonitorCheck = {
  success: boolean
}

type CheckList = {
  items: MonitorCheck[]
  total: number
}

type Incident = {
  id: string
  status: "open" | "acknowledged" | "resolved"
  duration_seconds: number
}

type IncidentList = {
  items: Incident[]
  total: number
}

function uniqueEmail(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`
}

async function register(page: Page, email: string): Promise<void> {
  await page.goto("/register")
  await expect(page).toHaveURL(/\/register$/)
  await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Dashboard" })).toHaveCount(0)
  await page.getByLabel("Email address").fill(email)
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD)
  await page.getByLabel("Confirm password", { exact: true }).fill(PASSWORD)
  await Promise.all([
    page.waitForURL(/\/dashboard$/),
    page.getByRole("button", { name: "Create account" }).click(),
  ])
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible()
}

async function login(page: Page, email: string): Promise<void> {
  await page.goto("/login")
  await page.getByLabel("Email address").fill(email)
  await page.getByLabel("Password", { exact: true }).fill("wrong-password")
  await page.getByRole("button", { name: "Log in" }).click()
  await expect(page.locator(".auth-status[role='alert']")).toContainText("Invalid email or password")
  await expect(page).toHaveURL(/\/login$/)

  await page.getByLabel("Password", { exact: true }).fill(PASSWORD)
  await Promise.all([
    page.waitForURL(/\/dashboard$/),
    page.getByRole("button", { name: "Log in" }).click(),
  ])
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible()
}

async function readJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(`${API_BASE_URL}${path}`)
  expect(response.ok(), `GET ${path} returned ${response.status()}`).toBeTruthy()
  return response.json() as Promise<T>
}

async function monitorList(page: Page): Promise<MonitorList> {
  return readJson(page, "/monitors?page=1&page_size=10")
}

async function checks(page: Page, monitorId: string): Promise<CheckList> {
  return readJson(page, `/monitors/${monitorId}/checks?page=1&page_size=100`)
}

async function incidents(page: Page, status: "open" | "resolved"): Promise<IncidentList> {
  return readJson(page, `/incidents?status=${status}&page=1&page_size=100`)
}

async function setTarget(page: Page, state: "healthy" | "fail"): Promise<void> {
  const response = await page.request.post(`${TARGET_CONTROL_URL}/__control/${state}`)
  expect(response.status()).toBe(204)
}

async function createMonitor(page: Page, name: string, url: string): Promise<void> {
  const response = await page.goto("/monitors/new")
  expect(response?.status()).toBe(200)
  await expect(page.getByRole("heading", { name: "Create monitor" })).toBeVisible()
  await page.getByLabel("Name").fill(name)
  await page.getByLabel("URL").fill(url)
  await page.getByLabel("Interval (seconds)").fill("3")
  await page.getByLabel("Timeout (seconds)").fill("2")
  await page.getByLabel("Failure threshold").fill("2")
  await page.getByLabel("Recovery threshold").fill("2")
  const submit = page.getByRole("button", { name: "Create monitor" })
  await Promise.all([
    page.waitForURL(/\/monitors$/),
    submit.evaluate((button: HTMLButtonElement) => {
      button.click()
      button.click()
    }),
  ])
  await expect(page.getByRole("link", { name })).toBeVisible()
}

test.describe.configure({ mode: "serial" })

test("complete MVP journey opens and recovers one incident", async ({ page, browser }) => {
  const browserErrors: string[] = []
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(message.text())
  })

  const email = uniqueEmail("journey")
  const monitorName = `Journey monitor ${Date.now()}`
  await setTarget(page, "healthy")
  await register(page, email)

  await page.getByRole("button", { name: "Log out" }).click()
  await expect(page).toHaveURL(/\/login$/)
  await login(page, email)
  browserErrors.length = 0

  await createMonitor(page, monitorName, "http://93.184.216.34:8080/health")
  const created = await monitorList(page)
  expect(created.total).toBe(1)
  expect(created.items).toHaveLength(1)
  const monitorId = created.items[0].id

  await expect.poll(async () => (await monitorList(page)).items[0]?.status, {
    message: "healthy check should move monitor to up",
    timeout: 30_000,
  }).toBe("up")
  const healthyChecks = await checks(page, monitorId)
  expect(healthyChecks.total).toBeGreaterThanOrEqual(1)
  expect(healthyChecks.items[0].success).toBe(true)

  await page.getByRole("link", { name: monitorName }).click()
  await expect(page.getByRole("heading", { name: monitorName })).toBeVisible()
  await expect(page.getByText("Up", { exact: true })).toBeVisible()
  await expect(page.getByRole("region", { name: "Monitor response-time history" })).toBeVisible()
  await expect(page.getByRole("region", { name: "Monitor check history" })).toBeVisible()
  await expect(page.getByText("Success", { exact: true }).first()).toBeVisible()

  const beforeFailureCount = healthyChecks.total
  await setTarget(page, "fail")
  await expect.poll(async () => {
    const history = await checks(page, monitorId)
    return history.total > beforeFailureCount && history.items[0].success === false
  }, { message: "first controlled failure should complete", timeout: 30_000 }).toBe(true)
  expect((await incidents(page, "open")).total).toBe(0)

  await expect.poll(async () => (await monitorList(page)).items[0]?.status, {
    message: "second controlled failure should reach threshold",
    timeout: 30_000,
  }).toBe("down")
  const opened = await incidents(page, "open")
  expect(opened.total).toBe(1)
  expect(opened.items).toHaveLength(1)
  const incidentId = opened.items[0].id

  await page.goto("/dashboard")
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible()
  await expect(page.getByText("Active incidents", { exact: true })).toBeVisible()
  await expect(page.locator('a[href^="/monitors/incidents/"]').filter({ hasText: monitorName })).toBeVisible()

  await page.goto("/monitors/incidents")
  await expect(page.getByRole("heading", { name: "Incident history" })).toBeVisible()
  await expect(page.getByText("1 incidents").first()).toBeVisible()
  await page.getByRole("link", { name: "unexpected status" }).click()
  await expect(page).toHaveURL(new RegExp(`/monitors/incidents/${incidentId}$`))
  await expect(page.getByText("Triggering failure", { exact: true })).toBeVisible()
  await expect(page.getByText("Incident timeline", { exact: true })).toBeVisible()
  await expect(page.getByText("opened", { exact: true })).toBeVisible()

  const failuresBeforeRecovery = (await checks(page, monitorId)).total
  await setTarget(page, "healthy")
  await expect.poll(async () => {
    const history = await checks(page, monitorId)
    const monitor = (await monitorList(page)).items[0]
    return history.total > failuresBeforeRecovery
      && history.items[0].success === true
      && monitor.status === "down"
  }, { message: "first recovery check should not resolve early", timeout: 30_000 }).toBe(true)
  expect((await incidents(page, "open")).total).toBe(1)

  await expect.poll(async () => (await monitorList(page)).items[0]?.status, {
    message: "second recovery check should move monitor to up",
    timeout: 30_000,
  }).toBe("up")
  expect((await incidents(page, "open")).total).toBe(0)
  const resolved = await incidents(page, "resolved")
  expect(resolved.total).toBe(1)
  expect(resolved.items[0].id).toBe(incidentId)
  const stableDuration = resolved.items[0].duration_seconds

  await page.reload()
  await expect(page.getByText("Recovery check", { exact: true })).toBeVisible()
  await expect(page.getByText("resolved", { exact: true }).first()).toBeVisible()
  await page.waitForTimeout(1_100)
  expect((await incidents(page, "resolved")).items[0].duration_seconds).toBe(stableDuration)

  await page.goto("/monitors/incidents")
  await expect(page.getByText("1 incidents").last()).toBeVisible()
  await expect(page.getByText("resolved", { exact: true })).toBeVisible()

  await page.goto(`/monitors/${monitorId}`)
  await expect(page.getByText("Failure", { exact: true }).first()).toBeVisible()
  await expect(page.getByText("Success", { exact: true }).first()).toBeVisible()
  await expect(page.getByRole("img", { name: /Response time in milliseconds/ })).toBeVisible()

  const isolatedContext = await browser.newContext()
  const isolatedPage = await isolatedContext.newPage()
  await register(isolatedPage, uniqueEmail("isolated"))
  expect((await monitorList(isolatedPage)).total).toBe(0)
  expect((await incidents(isolatedPage, "open")).total).toBe(0)
  expect((await incidents(isolatedPage, "resolved")).total).toBe(0)
  await isolatedPage.goto("/monitors")
  await expect(isolatedPage.getByText("No monitors yet")).toBeVisible()
  await expect(isolatedPage.getByText(monitorName)).toHaveCount(0)
  await isolatedContext.close()

  await page.goto("/dashboard")
  await expect(page.getByText("No active incidents")).toBeVisible()
  expect(browserErrors).toEqual([])
  await page.getByRole("button", { name: "Log out" }).click()
  await expect(page).toHaveURL(/\/login$/)
  await page.goto(`/monitors/${monitorId}`)
  await expect(page).toHaveURL(/\/login\?next=/)
  await page.reload()
  await expect(page).toHaveURL(/\/login\?next=/)
})

test("validation, empty, and controlled error states stay in place", async ({ page }) => {
  await page.goto("/register")
  await page.getByLabel("Email address").fill("invalid")
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD)
  await page.getByLabel("Confirm password", { exact: true }).fill("different-password")
  await page.getByRole("button", { name: "Create account" }).click()
  await expect(page.getByText("Enter a valid email address.")).toBeVisible()
  await expect(page.getByText("Passwords do not match.")).toBeVisible()
  await expect(page).toHaveURL(/\/register$/)

  await register(page, uniqueEmail("errors"))
  await page.goto("/monitors")
  await expect(page.getByText("No monitors yet")).toBeVisible()
  await page.goto("/monitors/incidents")
  await expect(page.getByText("No open incidents match these filters.")).toBeVisible()
  await expect(page.getByText("No resolved incidents match these filters.")).toBeVisible()

  await page.goto("/monitors/new")
  await page.getByLabel("Name").fill("Unsafe monitor")
  await page.getByLabel("URL").fill("http://127.0.0.1/health")
  await page.getByRole("button", { name: "Create monitor" }).click()
  await expect(page.getByText("Monitor URL must resolve to a public destination.", { exact: true })).toBeVisible()
  await expect(page).toHaveURL(/\/monitors\/new$/)

  await page.route(`${API_BASE_URL}/monitors`, async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ status: 503, contentType: "application/json", body: "{}" })
    } else {
      await route.continue()
    }
  })
  await page.getByLabel("Name").fill("Unavailable monitor")
  await page.getByLabel("URL").fill("http://93.184.216.34:8080/health")
  await page.getByRole("button", { name: "Create monitor" }).click()
  await expect(page.getByText("Monitor storage is temporarily unavailable. Try again.")).toBeVisible()
  await expect(page).toHaveURL(/\/monitors\/new$/)
  expect((await monitorList(page)).total).toBe(0)
  await page.unroute(`${API_BASE_URL}/monitors`)

  await page.route(`${API_BASE_URL}/monitors?**`, (route) => route.fulfill({
    status: 503,
    contentType: "application/json",
    body: "{}",
  }))
  await page.goto("/monitors")
  await expect(page.getByRole("heading", { name: "Unable to load monitors" })).toBeVisible()
})
