"use client";

import {
  ArrowRight,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent } from "react";
import { useEffect, useId, useState } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import type { AuthOutcome, CurrentUser } from "@/lib/auth-api";
import { loginUser, registerUser } from "@/lib/auth-api";
import { authRouteWithNext } from "@/lib/auth-redirect";

type Mode = "login" | "register";
type Tone = "idle" | "loading" | "success" | "error";
type AuthCopy = {
  title: string;
  description: string;
  submit: string;
  success: string;
  statusIntro: string;
  alternateLabel: string;
  alternateHref: "/login" | "/register";
  alternateText: string;
};

const COPY = {
  login: {
    title: "Welcome back",
    description: "Log in to your monitoring console",
    submit: "Log in",
    success: "Signed in. Redirecting…",
    statusIntro: "Ready to sign in",
    alternateLabel: "Don’t have an account?",
    alternateHref: "/register",
    alternateText: "Create one",
  },
  register: {
    title: "Create your account",
    description: "Create your account and enter your monitoring console.",
    submit: "Create account",
    success: "Account created. Redirecting…",
    statusIntro: "Ready to register",
    alternateLabel: "Already have an account?",
    alternateHref: "/login",
    alternateText: "Log in",
  },
} satisfies Record<Mode, AuthCopy>;

function validateEmail(value: string) {
  if (!value.trim()) return "Email is required.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return "Enter a valid email address.";
  return "";
}

function validatePassword(value: string) {
  if (!value) return "Password is required.";
  if (value.length < 8) return "Password must be at least 8 characters.";
  return "";
}

function retryMessage(retryAt: number, seconds: number) {
  const time = new Date(retryAt).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  });
  return `Too many attempts. Try again after ${time} (${seconds}s).`;
}

function PasswordToggle({
  visible,
  onToggle,
  label,
}: {
  visible: boolean;
  onToggle: () => void;
  label: string;
}) {
  const Icon = visible ? EyeOff : Eye;

  return (
    <button
      className="password-toggle"
      type="button"
      onClick={onToggle}
      aria-label={`${visible ? "Hide" : "Show"} ${label.toLowerCase()}`}
      aria-pressed={visible}
    >
      <Icon aria-hidden="true" />
    </button>
  );
}

export function AuthForm({
  mode,
  redirectTo = "/dashboard",
}: {
  mode: Mode;
  redirectTo?: string;
}) {
  const copy = COPY[mode];
  const router = useRouter();
  const formId = useId();
  const isRegister = mode === "register";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [touched, setTouched] = useState({ email: false, password: false, confirm: false });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [status, setStatus] = useState(copy.statusIntro);
  const [tone, setTone] = useState<Tone>("idle");
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [serverErrors, setServerErrors] = useState({ email: "", password: "" });
  const [retryAt, setRetryAt] = useState<number | null>(null);
  const [retrySeconds, setRetrySeconds] = useState(0);

  useEffect(() => {
    if (retryAt === null) return;
    const deadline = retryAt;

    function updateCountdown() {
      const seconds = Math.max(0, Math.ceil((deadline - Date.now()) / 1_000));
      setRetrySeconds(seconds);
      if (seconds === 0) {
        setRetryAt(null);
        setTone("idle");
        setStatus("You can try again now.");
      } else {
        setStatus(retryMessage(deadline, seconds));
      }
    }

    updateCountdown();
    const interval = window.setInterval(updateCountdown, 1_000);
    return () => window.clearInterval(interval);
  }, [retryAt]);

  const shouldValidate = (field: keyof typeof touched) => touched[field] || submitAttempted;
  const emailError = serverErrors.email || (shouldValidate("email") ? validateEmail(email) : "");
  const passwordError = serverErrors.password || (shouldValidate("password") ? validatePassword(password) : "");
  const confirmError =
    isRegister && shouldValidate("confirm")
      ? !confirmPassword
        ? "Confirm your password."
        : confirmPassword !== password
          ? "Passwords do not match."
          : ""
      : "";
  const readyToSubmit = Boolean(
    email.trim() && password && (!isRegister || confirmPassword),
  );

  function applyFailure(outcome: Exclude<AuthOutcome<CurrentUser>, { type: "success" }>) {
    setIsSubmitting(false);
    setTone("error");

    switch (outcome.type) {
      case "validation":
        setServerErrors({
          email: outcome.errors.find((error) => error.field === "email")?.message ?? "",
          password: outcome.errors.find((error) => error.field === "password")?.message ?? "",
        });
        setStatus(
          outcome.errors.find((error) => error.field === "form")?.message
          ?? "Fix the highlighted fields and try again.",
        );
        return;
      case "invalid_credentials":
        setStatus("Invalid email or password.");
        return;
      case "conflict":
        setServerErrors((current) => ({
          ...current,
          email: "An account with this email already exists.",
        }));
        setStatus("Fix the highlighted fields and try again.");
        return;
      case "rate_limited": {
        const deadline = Date.now() + outcome.retryAfterSeconds * 1_000;
        setRetrySeconds(outcome.retryAfterSeconds);
        setRetryAt(deadline);
        setStatus(retryMessage(deadline, outcome.retryAfterSeconds));
        return;
      }
      case "unavailable":
        setStatus("Authentication is temporarily unavailable. Try again.");
        return;
      case "timeout":
        setStatus("The request timed out. Try again.");
        return;
      case "network_error":
        setStatus("Unable to reach the service. Check your connection and try again.");
        return;
      case "unauthenticated":
        setStatus("Your session expired. Log in again.");
        return;
      case "unexpected_response":
        setStatus("Unable to complete the request. Try again.");
        return;
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting || retrySeconds > 0) return;
    setSubmitAttempted(true);
    setServerErrors({ email: "", password: "" });

    const hasError = Boolean(
      validateEmail(email) ||
        validatePassword(password) ||
        (isRegister && (!confirmPassword || confirmPassword !== password)),
    );

    if (hasError) {
      setTouched({ email: true, password: true, confirm: true });
      setTone("error");
      setStatus("Fix the highlighted fields and try again.");
      return;
    }

    setIsSubmitting(true);
    setTone("loading");
    setStatus(isRegister ? "Creating account…" : "Signing in…");

    const outcome = isRegister
      ? await registerUser(email, password)
      : await loginUser(email, password);

    if (outcome.type !== "success") {
      applyFailure(outcome);
      return;
    }

    setIsSubmitting(false);
    setTone("success");
    setStatus(copy.success);
    router.replace(redirectTo);
    router.refresh();
  }

  return (
    <main className="auth-page">
      <ThemeToggle />

      <section className="auth-card" aria-labelledby={`${formId}-title`}>
        <Link className="auth-brand" href="/" aria-label="UptimeArc home">
          Uptime<span>Arc</span>
        </Link>

        <header className="auth-header">
          <h1 id={`${formId}-title`}>{copy.title}</h1>
          <p>{copy.description}</p>
        </header>

        <p className="auth-status" aria-live="polite" data-tone={tone}>
          {status}
        </p>

        <form className="auth-form" onSubmit={handleSubmit} noValidate aria-busy={isSubmitting}>
          <div className="auth-field" data-invalid={Boolean(emailError)}>
            <label htmlFor={`${formId}-email`}>Email address</label>
            <div className="input-shell">
              <Mail aria-hidden="true" />
              <input
                id={`${formId}-email`}
                type="email"
                inputMode="email"
                autoComplete="email"
                placeholder="name@company.com"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  setServerErrors((current) => ({ ...current, email: "" }));
                }}
                onBlur={() => setTouched((current) => ({ ...current, email: true }))}
                disabled={isSubmitting}
                aria-invalid={Boolean(emailError)}
                aria-describedby={emailError ? `${formId}-email-error` : undefined}
              />
            </div>
            {emailError ? <p id={`${formId}-email-error`} role="alert">{emailError}</p> : null}
          </div>

          <div className="auth-field" data-invalid={Boolean(passwordError)}>
            <label htmlFor={`${formId}-password`}>Password</label>
            <div className="input-shell">
              <LockKeyhole aria-hidden="true" />
              <input
                id={`${formId}-password`}
                type={showPassword ? "text" : "password"}
                autoComplete={isRegister ? "new-password" : "current-password"}
                placeholder="At least 8 characters"
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value);
                  setServerErrors((current) => ({ ...current, password: "" }));
                }}
                onBlur={() => setTouched((current) => ({ ...current, password: true }))}
                disabled={isSubmitting}
                aria-invalid={Boolean(passwordError)}
                aria-describedby={passwordError ? `${formId}-password-error` : undefined}
              />
              <PasswordToggle
                visible={showPassword}
                onToggle={() => setShowPassword((current) => !current)}
                label="password"
              />
            </div>
            {passwordError ? <p id={`${formId}-password-error`} role="alert">{passwordError}</p> : null}
          </div>

          {isRegister ? (
            <div className="auth-field" data-invalid={Boolean(confirmError)}>
              <label htmlFor={`${formId}-confirm`}>Confirm password</label>
              <div className="input-shell">
                <LockKeyhole aria-hidden="true" />
                <input
                  id={`${formId}-confirm`}
                  type={showConfirmPassword ? "text" : "password"}
                  autoComplete="new-password"
                  placeholder="Repeat your password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  onBlur={() => setTouched((current) => ({ ...current, confirm: true }))}
                  disabled={isSubmitting}
                  aria-invalid={Boolean(confirmError)}
                  aria-describedby={confirmError ? `${formId}-confirm-error` : undefined}
                />
                <PasswordToggle
                  visible={showConfirmPassword}
                  onToggle={() => setShowConfirmPassword((current) => !current)}
                  label="confirm password"
                />
              </div>
              {confirmError ? <p id={`${formId}-confirm-error`} role="alert">{confirmError}</p> : null}
            </div>
          ) : null}

          <button
            className="auth-submit"
            type="submit"
            disabled={isSubmitting || retrySeconds > 0 || !readyToSubmit}
          >
            <span>
              {isSubmitting
                ? "Working…"
                : retrySeconds > 0
                  ? `Try again in ${retrySeconds}s`
                  : copy.submit}
            </span>
            <ArrowRight aria-hidden="true" />
          </button>
        </form>

        <footer className="auth-footer">
          <span>{copy.alternateLabel}</span>
          <Link href={authRouteWithNext(copy.alternateHref, redirectTo)}>
            {copy.alternateText}
          </Link>
        </footer>
      </section>
    </main>
  );
}
