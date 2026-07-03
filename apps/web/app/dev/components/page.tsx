import Link from "next/link";

export default function DevComponentsPage() {
  return (
    <main className="compact-page">
      <div className="compact-grid">
        <section className="compact-panel">
          <p className="eyebrow">Component preview</p>
          <h1 className="hero-title">Auth states</h1>
          <p className="hero-copy">
            Quick local preview for the login and registration surfaces. Useful for checking
            validation, loading, and disabled states without moving through the full app.
          </p>
          <p className="surface-note">
            <Link className="form-link" href="/login">
              Back to login
            </Link>
          </p>
        </section>

        <section className="compact-panel">
          <p className="form-kicker">Routes</p>
          <p className="hero-copy">
            <Link className="form-link" href="/login">
              /login
            </Link>{" "}
            and{" "}
            <Link className="form-link" href="/register">
              /register
            </Link>{" "}
            share one form implementation and one responsive layout.
          </p>
        </section>
      </div>
    </main>
  );
}
