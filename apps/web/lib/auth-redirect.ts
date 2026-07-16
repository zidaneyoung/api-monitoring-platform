const APP_ORIGIN = "http://app.local"

function decodeForSafety(value: string): string | null {
  let decoded = value

  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const next = decodeURIComponent(decoded)
      if (next === decoded) return decoded
      decoded = next
    } catch {
      return null
    }
  }

  return decoded
}

function isUnsafeDestination(value: string): boolean {
  return (
    !value.startsWith("/")
    || value.startsWith("//")
    || value.includes("\\")
    || /[\u0000-\u001f\u007f]/.test(value)
  )
}

export function safeAuthRedirect(destination: string | undefined): string {
  if (!destination || isUnsafeDestination(destination)) return "/dashboard"

  const decoded = decodeForSafety(destination)
  if (!decoded || isUnsafeDestination(decoded)) return "/dashboard"

  try {
    const originalUrl = new URL(destination, APP_ORIGIN)
    const decodedUrl = new URL(decoded, APP_ORIGIN)
    if (originalUrl.origin !== APP_ORIGIN || decodedUrl.origin !== APP_ORIGIN) {
      return "/dashboard"
    }

    return `${originalUrl.pathname}${originalUrl.search}${originalUrl.hash}`
  } catch {
    return "/dashboard"
  }
}

export function authRouteWithNext(
  route: "/login" | "/register",
  destination: string | undefined,
): string {
  const safeDestination = safeAuthRedirect(destination)
  return safeDestination === "/dashboard"
    ? route
    : `${route}?next=${encodeURIComponent(safeDestination)}`
}
