"use client";

import Link from "next/link";
import type { FormEvent } from "react";
import { useEffect, useId, useRef, useState } from "react";

type Mode = "login" | "register";

type AuthCopy = {
  eyebrow: string;
  title: string;
  description: string;
  submit: string;
  success: string;
  statusIntro: string;
  alternateLabel: string;
  alternateHref: string;
  alternateText: string;
  helperText: string;
};

const COPY: Record<Mode, AuthCopy> = {
  login: {
    eyebrow: "Return access",
    title: "Log in to the monitoring console",
    description:
      "Mock sign-in flow. Validate the form, trigger loading, and confirm the disabled button state without any real authentication call.",
    submit: "Log in",
    success: "Mock login complete. No session was created.",
    statusIntro: "Ready to sign in",
    alternateLabel: "Need an account?",
    alternateHref: "/register",
    alternateText: "Create one",
    helperText: "Use any valid email address and a password with at least 8 characters.",
  },
  register: {
    eyebrow: "Create access",
    title: "Set up a new account",
    description:
      "Mock registration flow. The form behaves like production UI, but it never sends a network request or creates a real account.",
    submit: "Create account",
    success: "Mock registration complete. No account was created.",
    statusIntro: "Ready to register",
    alternateLabel: "Already registered?",
    alternateHref: "/login",
    alternateText: "Go to login",
    helperText: "Use any valid email address and a password with at least 8 characters.",
  },
};

function validateEmail(value: string) {
  if (!value.trim()) {
    return "Email is required.";
  }

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
    return "Enter a valid email address.";
  }

  return "";
}

function validatePassword(value: string) {
  if (!value) {
    return "Password is required.";
  }

  if (value.length < 8) {
    return "Password must be at least 8 characters.";
  }

  return "";
}

export function AuthForm({ mode }: { mode: Mode }) {
  const copy = COPY[mode];
  const formId = useId();
  const emailId = `${formId}-email`;
  const passwordId = `${formId}-password`;
  const emailHintId = `${formId}-email-hint`;
  const passwordHintId = `${formId}-password-hint`;
  const statusId = `${formId}-status`;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState({ email: false, password: false });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [status, setStatus] = useState(copy.statusIntro);
  const [tone, setTone] = useState<"idle" | "success" | "error">("idle");
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const submitTimer = useRef<number | null>(null);

  useEffect(() => {
    setStatus(copy.statusIntro);
    setTone("idle");
    setSubmitAttempted(false);
    setEmail("");
    setPassword("");
    setTouched({ email: false, password: false });
    setIsSubmitting(false);
  }, [copy.statusIntro, mode]);

  useEffect(() => {
    return () => {
      if (submitTimer.current !== null) {
        window.clearTimeout(submitTimer.current);
      }
    };
  }, []);

  const emailError = touched.email || submitAttempted ? validateEmail(email) : "";
  const passwordError = touched.password || submitAttempted ? validatePassword(password) : "";
  const readyToSubmit = Boolean(email.trim() && password.trim());
  const submitDisabled = isSubmitting || !readyToSubmit;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitAttempted(true);

    const nextEmailError = validateEmail(email);
    const nextPasswordError = validatePassword(password);

    if (nextEmailError || nextPasswordError) {
      setTouched({ email: true, password: true });
      setTone("error");
      setStatus("Fix the highlighted fields and try again.");
      return;
    }

    setIsSubmitting(true);
    setTone("idle");
    setStatus("Submitting mock request...");

    if (submitTimer.current !== null) {
      window.clearTimeout(submitTimer.current);
    }

    submitTimer.current = window.setTimeout(() => {
      setIsSubmitting(false);
      setTone("success");
      setStatus(copy.success);
      setSubmitAttempted(false);
      setTouched({ email: false, password: false });
      submitTimer.current = null;
    }, 1200);
  }

  return (
    <section className="auth-page" aria-labelledby={`${formId}-title`}>
      <div className="auth-shell">
        <aside className="auth-hero">
          <div>
            <p className="eyebrow">{copy.eyebrow}</p>
            <h1 className="hero-title">API monitoring with clean auth flows</h1>
            <p className="hero-copy">
              Built for demo states: validation, loading, disabled controls, and responsive
              layout all work without any backend dependency.
            </p>
            <ul className="hero-list">
              <li>
                <span className="hero-dot" aria-hidden="true" />
                <span>Accessible labels, helper text, and live validation copy.</span>
              </li>
              <li>
                <span className="hero-dot" aria-hidden="true" />
                <span>Buttons switch between disabled, loading, and ready states.</span>
              </li>
              <li>
                <span className="hero-dot" aria-hidden="true" />
                <span>Mobile layout stacks without losing spacing or focus clarity.</span>
              </li>
            </ul>
          </div>

          <div className="hero-footer">
            <span className="chip">Mock submission only</span>
            <span className="chip">Email + password</span>
            <span className="chip">No network request</span>
          </div>
        </aside>

        <div className="auth-card">
          <div className="auth-card-inner">
            <div className="form-header">
              <span className="form-kicker">{copy.eyebrow}</span>
              <h2 id={`${formId}-title`} className="form-title">
                {copy.title}
              </h2>
              <p className="form-copy">{copy.description}</p>
            </div>

            <p
              id={statusId}
              className="status-banner"
              aria-live="polite"
              data-tone={tone}
            >
              {status}
            </p>

            <form className="auth-form" onSubmit={handleSubmit} noValidate aria-busy={isSubmitting}>
              <div className="field">
                <label className="field-label" htmlFor={emailId}>
                  Email address
                </label>
                <input
                  id={emailId}
                  className="field-input"
                  type="email"
                  autoComplete="email"
                  inputMode="email"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  onBlur={() => setTouched((current) => ({ ...current, email: true }))}
                  disabled={isSubmitting}
                  aria-invalid={Boolean(emailError)}
                  aria-describedby={`${emailHintId} ${statusId}`}
                />
                <p
                  id={emailHintId}
                  className="field-message"
                  data-tone={emailError ? "error" : "idle"}
                >
                  {emailError || copy.helperText}
                </p>
              </div>

              <div className="field">
                <label className="field-label" htmlFor={passwordId}>
                  Password
                </label>
                <input
                  id={passwordId}
                  className="field-input"
                  type="password"
                  autoComplete={mode === "login" ? "current-password" : "new-password"}
                  placeholder="At least 8 characters"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  onBlur={() => setTouched((current) => ({ ...current, password: true }))}
                  disabled={isSubmitting}
                  aria-invalid={Boolean(passwordError)}
                  aria-describedby={`${passwordHintId} ${statusId}`}
                />
                <p
                  id={passwordHintId}
                  className="field-message"
                  data-tone={passwordError ? "error" : "idle"}
                >
                  {passwordError || "Password input obscures entered characters."}
                </p>
              </div>

              <div className="button-row">
                <button className="button button--primary" type="submit" disabled={submitDisabled}>
                  {isSubmitting ? "Working..." : copy.submit}
                </button>
                <button
                  className="button button--secondary"
                  type="button"
                  disabled
                  aria-disabled="true"
                  title="Intentional disabled example state"
                >
                  Disabled demo button
                </button>
              </div>
            </form>

            <div className="form-footer">
              <span>{copy.alternateLabel}</span>
              <Link className="form-link" href={copy.alternateHref}>
                {copy.alternateText}
              </Link>
            </div>

            <p className="surface-note">
              {mode === "login"
                ? "Mock sign-in updates local component state only."
                : "Mock sign-up updates local component state only."}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
