"use client";

import {
  ArrowRight,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent } from "react";
import { useId, useState } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import { loginUser, registerUser } from "@/lib/auth-api";

type Mode = "login" | "register";
type Tone = "idle" | "loading" | "success" | "error";

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
    description: "Start monitoring in minutes.",
    submit: "Create account",
    success: "Account created. You can now log in.",
    statusIntro: "Ready to register",
    alternateLabel: "Already have an account?",
    alternateHref: "/login",
    alternateText: "Log in",
  },
} satisfies Record<Mode, Record<string, string>>;

function validateName(value: string) {
  if (!value.trim()) return "Full name is required.";
  if (value.trim().length < 2) return "Enter your full name.";
  return "";
}

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

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [touched, setTouched] = useState({ name: false, email: false, password: false, confirm: false });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [status, setStatus] = useState(copy.statusIntro);
  const [tone, setTone] = useState<Tone>("idle");
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [serverErrors, setServerErrors] = useState({ email: "", password: "" });

  const shouldValidate = (field: keyof typeof touched) => touched[field] || submitAttempted;
  const nameError = isRegister && shouldValidate("name") ? validateName(name) : "";
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
    email.trim() && password && (!isRegister || (name.trim() && confirmPassword)),
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitAttempted(true);
    setServerErrors({ email: "", password: "" });

    const hasError = Boolean(
      validateEmail(email) ||
        validatePassword(password) ||
        (isRegister && (validateName(name) || !confirmPassword || confirmPassword !== password)),
    );

    if (hasError) {
      setTouched({ name: true, email: true, password: true, confirm: true });
      setTone("error");
      setStatus("Fix the highlighted fields and try again.");
      return;
    }

    setIsSubmitting(true);
    setTone("loading");
    setStatus(isRegister ? "Creating account…" : "Signing in…");

    if (isRegister) {
      const errors = await registerUser(email, password);
      setIsSubmitting(false);

      if (errors.length > 0) {
        setServerErrors({
          email: errors.find((error) => error.field === "email")?.message ?? "",
          password: errors.find((error) => error.field === "password")?.message ?? "",
        });
        setTone("error");
        setStatus(errors.find((error) => error.field === "form")?.message ?? "Fix the highlighted fields and try again.");
        return;
      }

      setTone("success");
      setStatus(copy.success);
      setPassword("");
      setConfirmPassword("");
      setSubmitAttempted(false);
      setTouched({ name: false, email: false, password: false, confirm: false });
      return;
    }

    const errors = await loginUser(email, password);
    setIsSubmitting(false);

    if (errors.length > 0) {
      setServerErrors({
        email: errors.find((error) => error.field === "email")?.message ?? "",
        password: errors.find((error) => error.field === "password")?.message ?? "",
      });
      setTone("error");
      setStatus(errors.find((error) => error.field === "form")?.message ?? "Fix the highlighted fields and try again.");
      return;
    }

    setTone("success");
    setStatus(copy.success);
    router.replace(redirectTo);
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
          {isRegister ? (
            <div className="auth-field" data-invalid={Boolean(nameError)}>
              <label htmlFor={`${formId}-name`}>Full name</label>
              <div className="input-shell">
                <UserRound aria-hidden="true" />
                <input
                  id={`${formId}-name`}
                  type="text"
                  autoComplete="name"
                  placeholder="John Doe"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  onBlur={() => setTouched((current) => ({ ...current, name: true }))}
                  disabled={isSubmitting}
                  aria-invalid={Boolean(nameError)}
                  aria-describedby={nameError ? `${formId}-name-error` : undefined}
                />
              </div>
              {nameError ? <p id={`${formId}-name-error`} role="alert">{nameError}</p> : null}
            </div>
          ) : null}

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

          <button className="auth-submit" type="submit" disabled={isSubmitting || !readyToSubmit}>
            <span>{isSubmitting ? "Working…" : copy.submit}</span>
            <ArrowRight aria-hidden="true" />
          </button>
        </form>

        <footer className="auth-footer">
          <span>{copy.alternateLabel}</span>
          <Link href={copy.alternateHref}>{copy.alternateText}</Link>
        </footer>
      </section>
    </main>
  );
}
