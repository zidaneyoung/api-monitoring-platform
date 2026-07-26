const requiredVariables = ["INTERNAL_API_BASE_URL", "SESSION_COOKIE_NAME"]
const missingVariables = requiredVariables.filter(
  (name) => !process.env[name]?.trim(),
)

function fail(message) {
  process.stderr.write(`${message}\n`)
  process.exit(1)
}

if (missingVariables.length > 0) {
  fail(
    `Missing required production frontend environment variables: ${missingVariables.join(", ")}`,
  )
}

let internalApiUrl
try {
  internalApiUrl = new URL(process.env.INTERNAL_API_BASE_URL)
} catch {
  fail("INTERNAL_API_BASE_URL must be an absolute HTTP or HTTPS URL")
}

if (!["http:", "https:"].includes(internalApiUrl.protocol)) {
  fail("INTERNAL_API_BASE_URL must be an absolute HTTP or HTTPS URL")
}

const cookieNamePattern = /^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$/
if (!cookieNamePattern.test(process.env.SESSION_COOKIE_NAME)) {
  fail("SESSION_COOKIE_NAME must be a valid cookie name")
}

await import("./server.js")
