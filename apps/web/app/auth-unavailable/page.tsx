import { ArrowRight, RotateCw } from "lucide-react";
import Link from "next/link";

import { ThemeToggle } from "@/components/theme-toggle";
import { authRouteWithNext, safeAuthRedirect } from "@/lib/auth-redirect";

export default async function AuthenticationUnavailablePage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const next = (await searchParams).next;
  const requestedDestination = Array.isArray(next) ? next[0] : next;
  const destination = safeAuthRedirect(requestedDestination);

  return (
    <main className="auth-page">
      <ThemeToggle />

      <section className="auth-card" aria-labelledby="auth-unavailable-title">
        <Link className="auth-brand" href="/" aria-label="UptimeArc home">
          Uptime<span>Arc</span>
        </Link>

        <header className="auth-header">
          <h1 id="auth-unavailable-title">We can’t verify your session</h1>
          <p>Your account may still be signed in. The service is temporarily unavailable.</p>
        </header>

        <p className="auth-status" data-tone="error" role="alert">
          Protected content has not been loaded. Try again when the service is reachable.
        </p>

        <div className="auth-unavailable-actions">
          <Link className="auth-submit" href={destination}>
            <span>Try again</span>
            <RotateCw aria-hidden="true" />
          </Link>

          <footer className="auth-footer">
            <span>Need to use a different account?</span>
            <Link href={authRouteWithNext("/login", destination)}>
              Go to login <ArrowRight aria-hidden="true" />
            </Link>
          </footer>
        </div>
      </section>
    </main>
  );
}
