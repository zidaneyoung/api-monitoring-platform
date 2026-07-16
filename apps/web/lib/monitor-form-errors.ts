import {
  type MonitorCreatePayload,
  type MonitorError,
  type MonitorField,
  type MonitorOutcome,
} from "@/lib/monitor-api"


export type MonitorFormErrorCategory =
  | "authentication"
  | "authorization"
  | "not_found"
  | "validation"
  | "conflict"
  | "rate_limit"
  | "internal_error"
  | "network"
  | "unknown"

export type MonitorFormErrors = {
  category: MonitorFormErrorCategory
  fieldErrors: MonitorError[]
  generalErrors: string[]
}

type MonitorFormAction = "create" | "edit"
type MonitorFailureOutcome = Exclude<MonitorOutcome<unknown>, { type: "success" }>

const NUMERIC_RULES: Array<{
  field: Exclude<MonitorField, "name" | "url" | "http_method" | "form">
  label: string
  minimum: number
  maximum: number
}> = [
  { field: "interval_seconds", label: "Interval", minimum: 1, maximum: 86_400 },
  { field: "timeout_seconds", label: "Timeout", minimum: 1, maximum: 300 },
  { field: "expected_status_min", label: "Minimum accepted status", minimum: 100, maximum: 599 },
  { field: "expected_status_max", label: "Maximum accepted status", minimum: 100, maximum: 599 },
  { field: "failure_threshold", label: "Failure threshold", minimum: 1, maximum: 100 },
  { field: "recovery_threshold", label: "Recovery threshold", minimum: 1, maximum: 100 },
]

function generalMessage(type: MonitorFailureOutcome["type"], action: MonitorFormAction): string {
  const operation = action === "edit" ? "updated" : "created"
  if (type === "unauthenticated") return "Your session has expired. Sign in and try again."
  if (type === "forbidden") return "You do not have permission to change this monitor."
  if (type === "not_found") return "This monitor no longer exists or is not available to your account."
  if (type === "conflict") return "This monitor changed before your request completed. Review it and try again."
  if (type === "rate_limited") return "Too many monitor requests were submitted. Wait a moment and try again."
  if (type === "internal_error" || type === "unavailable") {
    return "Monitor storage is temporarily unavailable. Try again."
  }
  if (type === "timeout") return "The request timed out. Try again."
  if (type === "network_error") return "Unable to reach the service. Check your connection and try again."
  return `The monitor could not be ${operation}. Try again.`
}

export function emptyMonitorFormErrors(): MonitorFormErrors {
  return { category: "validation", fieldErrors: [], generalErrors: [] }
}

export function adaptMonitorFormFailure(
  outcome: MonitorFailureOutcome,
  action: MonitorFormAction,
): MonitorFormErrors {
  if (outcome.type === "validation") {
    return {
      category: "validation",
      fieldErrors: outcome.errors.filter((error) => error.field !== "form"),
      generalErrors: outcome.errors
        .filter((error) => error.field === "form")
        .map((error) => error.message),
    }
  }

  const categories: Partial<Record<MonitorFailureOutcome["type"], MonitorFormErrorCategory>> = {
    unauthenticated: "authentication",
    forbidden: "authorization",
    not_found: "not_found",
    conflict: "conflict",
    rate_limited: "rate_limit",
    internal_error: "internal_error",
    unavailable: "internal_error",
    timeout: "network",
    network_error: "network",
    unexpected_response: "unknown",
  }

  return {
    category: categories[outcome.type] ?? "unknown",
    fieldErrors: [],
    generalErrors: [generalMessage(outcome.type, action)],
  }
}

export function validateMonitorPayload(payload: MonitorCreatePayload): MonitorFormErrors | null {
  const fieldErrors: MonitorError[] = []
  const addError = (field: MonitorField, message: string) => fieldErrors.push({ field, message })

  const name = payload.name.trim()
  if (!name) addError("name", "Enter a monitor name.")
  else if (name.length > 200) addError("name", "Use 200 characters or fewer.")

  const url = payload.url.trim()
  if (!url) {
    addError("url", "Enter an HTTP or HTTPS URL.")
  } else if (url.length > 2_048) {
    addError("url", "Use a URL with 2048 characters or fewer.")
  } else {
    try {
      const parsed = new URL(url)
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        addError("url", "Enter an HTTP or HTTPS URL.")
      }
    } catch {
      addError("url", "Enter a valid HTTP or HTTPS URL.")
    }
  }

  for (const rule of NUMERIC_RULES) {
    const value = payload[rule.field]
    if (!Number.isInteger(value) || value < rule.minimum || value > rule.maximum) {
      addError(
        rule.field,
        `${rule.label} must be a whole number between ${rule.minimum} and ${rule.maximum}.`,
      )
    }
  }

  const statusValuesAreValid = [payload.expected_status_min, payload.expected_status_max]
    .every((value) => Number.isInteger(value) && value >= 100 && value <= 599)
  if (statusValuesAreValid && payload.expected_status_min > payload.expected_status_max) {
    const message = "Minimum accepted status must not exceed maximum accepted status."
    addError("expected_status_min", message)
    addError("expected_status_max", message)
  }

  return fieldErrors.length
    ? { category: "validation", fieldErrors, generalErrors: [] }
    : null
}
