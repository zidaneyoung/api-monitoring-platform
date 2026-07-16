import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

import { safeAuthRedirect } from "@/lib/auth-redirect"


const SESSION_COOKIE_NAME = process.env.SESSION_COOKIE_NAME ?? "amp_session"
const INTERNAL_API_BASE_URL = process.env.INTERNAL_API_BASE_URL ?? "http://localhost:8000"
const AUTH_CHECK_TIMEOUT_MS = 5_000
const GUEST_ROUTES = new Set(["/login", "/register"])

function copySessionCookie(source: Response, destination: NextResponse): void {
  const sessionCookie = source.headers.get("set-cookie")
  if (sessionCookie) destination.headers.append("set-cookie", sessionCookie)
}

function noStore(response: NextResponse): NextResponse {
  response.headers.set("Cache-Control", "no-store")
  return response
}

function requestDestination(request: NextRequest): string {
  return `${request.nextUrl.pathname}${request.nextUrl.search}`
}

function guestDestination(request: NextRequest): string {
  return safeAuthRedirect(request.nextUrl.searchParams.get("next") ?? undefined)
}

function redirectToLogin(request: NextRequest, authResponse?: Response): NextResponse {
  const loginUrl = new URL("/login", request.url)
  loginUrl.searchParams.set("next", requestDestination(request))
  const response = noStore(NextResponse.redirect(loginUrl))
  if (authResponse) copySessionCookie(authResponse, response)
  return response
}

function redirectToUnavailable(request: NextRequest, destination: string): NextResponse {
  const unavailableUrl = new URL("/auth-unavailable", request.url)
  unavailableUrl.searchParams.set("next", safeAuthRedirect(destination))
  return noStore(NextResponse.redirect(unavailableUrl))
}

async function verifySession(request: NextRequest, token: string): Promise<Response | null> {
  try {
    return await fetch(`${INTERNAL_API_BASE_URL}/auth/me`, {
      method: "GET",
      headers: { Cookie: `${SESSION_COOKIE_NAME}=${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(AUTH_CHECK_TIMEOUT_MS),
    })
  } catch {
    return null
  }
}

export async function proxy(request: NextRequest): Promise<NextResponse> {
  const isGuestRoute = GUEST_ROUTES.has(request.nextUrl.pathname)
  const session = request.cookies.get(SESSION_COOKIE_NAME)

  if (!session?.value) {
    return isGuestRoute
      ? noStore(NextResponse.next())
      : redirectToLogin(request)
  }

  const authResponse = await verifySession(request, session.value)
  if (authResponse === null) {
    return redirectToUnavailable(
      request,
      isGuestRoute ? guestDestination(request) : requestDestination(request),
    )
  }

  if (authResponse.ok) {
    if (isGuestRoute) {
      const response = noStore(
        NextResponse.redirect(new URL(guestDestination(request), request.url)),
      )
      copySessionCookie(authResponse, response)
      return response
    }

    const response = noStore(NextResponse.next())
    copySessionCookie(authResponse, response)
    return response
  }

  if (authResponse.status === 401) {
    if (isGuestRoute) {
      const response = noStore(NextResponse.next())
      copySessionCookie(authResponse, response)
      return response
    }
    return redirectToLogin(request, authResponse)
  }

  return redirectToUnavailable(
    request,
    isGuestRoute ? guestDestination(request) : requestDestination(request),
  )
}

export const config = {
  matcher: ["/dashboard/:path*", "/monitors/:path*", "/login", "/register"],
}
