import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"


const SESSION_COOKIE_NAME = process.env.SESSION_COOKIE_NAME ?? "amp_session"
const INTERNAL_API_BASE_URL = process.env.INTERNAL_API_BASE_URL ?? "http://localhost:8000"
const AUTH_CHECK_TIMEOUT_MS = 5_000

function copySessionCookie(source: Response, destination: NextResponse): void {
  const sessionCookie = source.headers.get("set-cookie")
  if (sessionCookie) destination.headers.append("set-cookie", sessionCookie)
}

function redirectToLogin(request: NextRequest, authResponse?: Response): NextResponse {
  const loginUrl = new URL("/login", request.url)
  loginUrl.searchParams.set(
    "next",
    `${request.nextUrl.pathname}${request.nextUrl.search}`,
  )
  const response = NextResponse.redirect(loginUrl)
  response.headers.set("Cache-Control", "no-store")
  if (authResponse) copySessionCookie(authResponse, response)
  return response
}

export async function proxy(request: NextRequest): Promise<NextResponse> {
  const session = request.cookies.get(SESSION_COOKIE_NAME)
  if (!session?.value) return redirectToLogin(request)

  let authResponse: Response
  try {
    authResponse = await fetch(`${INTERNAL_API_BASE_URL}/auth/me`, {
      method: "GET",
      headers: { Cookie: `${SESSION_COOKIE_NAME}=${session.value}` },
      cache: "no-store",
      signal: AbortSignal.timeout(AUTH_CHECK_TIMEOUT_MS),
    })
  } catch {
    return redirectToLogin(request)
  }

  if (!authResponse.ok) return redirectToLogin(request, authResponse)

  const response = NextResponse.next()
  response.headers.set("Cache-Control", "no-store")
  copySessionCookie(authResponse, response)
  return response
}

export const config = {
  matcher: ["/dashboard/:path*", "/monitors/:path*"],
}
