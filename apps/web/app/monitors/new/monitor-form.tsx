"use client"

import { Loader2Icon } from "lucide-react"
import { useRouter } from "next/navigation"
import { useEffect, useRef, useState, type FormEvent, type MouseEvent } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  createMonitor,
  type MonitorCreatePayload,
  type MonitorDto,
  type MonitorField,
  updateMonitor,
} from "@/lib/monitor-api"
import {
  adaptMonitorFormFailure,
  emptyMonitorFormErrors,
  type MonitorFormErrors,
  validateMonitorPayload,
} from "@/lib/monitor-form-errors"


type MonitorInputField = Exclude<MonitorField, "form">

const FIELD_DETAILS: Record<MonitorInputField, { id: string; label: string }> = {
  name: { id: "monitor-name", label: "Name" },
  url: { id: "monitor-url", label: "URL" },
  http_method: { id: "monitor-method", label: "HTTP method" },
  interval_seconds: { id: "monitor-interval", label: "Interval (seconds)" },
  timeout_seconds: { id: "monitor-timeout", label: "Timeout (seconds)" },
  expected_status_min: { id: "monitor-status-min", label: "Minimum accepted status" },
  expected_status_max: { id: "monitor-status-max", label: "Maximum accepted status" },
  failure_threshold: { id: "monitor-failure-threshold", label: "Failure threshold" },
  recovery_threshold: { id: "monitor-recovery-threshold", label: "Recovery threshold" },
}

function numberValue(formData: FormData, field: MonitorField): number {
  return Number(formData.get(field))
}

function errorId(field: MonitorInputField): string {
  return `${FIELD_DETAILS[field].id}-error`
}

function describedBy(
  errors: MonitorFormErrors,
  field: MonitorInputField,
  descriptionId: string,
): string {
  return errors.fieldErrors.some((error) => error.field === field)
    ? `${descriptionId} ${errorId(field)}`
    : descriptionId
}

export function MonitorForm({ monitor }: { monitor?: MonitorDto }) {
  const router = useRouter()
  const [errors, setErrors] = useState<MonitorFormErrors>(emptyMonitorFormErrors)
  const [errorVersion, setErrorVersion] = useState(0)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const errorSummaryRef = useRef<HTMLDivElement>(null)
  const isEditing = monitor !== undefined

  useEffect(() => {
    if (errorVersion > 0) errorSummaryRef.current?.focus()
  }, [errorVersion])

  const errorsFor = (field: MonitorInputField) => (
    errors.fieldErrors.filter((error) => error.field === field)
  )
  const hasErrors = errors.fieldErrors.length > 0 || errors.generalErrors.length > 0

  function showErrors(nextErrors: MonitorFormErrors) {
    setErrors(nextErrors)
    setErrorVersion((version) => version + 1)
  }

  function focusField(event: MouseEvent<HTMLAnchorElement>, field: MonitorInputField) {
    event.preventDefault()
    document.getElementById(FIELD_DETAILS[field].id)?.focus()
  }

  async function submitMonitor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isSubmitting) return

    const formData = new FormData(event.currentTarget)
    const payload: MonitorCreatePayload = {
      name: String(formData.get("name") ?? ""),
      url: String(formData.get("url") ?? ""),
      http_method: formData.get("http_method") === "HEAD" ? "HEAD" : "GET",
      interval_seconds: numberValue(formData, "interval_seconds"),
      timeout_seconds: numberValue(formData, "timeout_seconds"),
      expected_status_min: numberValue(formData, "expected_status_min"),
      expected_status_max: numberValue(formData, "expected_status_max"),
      failure_threshold: numberValue(formData, "failure_threshold"),
      recovery_threshold: numberValue(formData, "recovery_threshold"),
    }

    const clientErrors = validateMonitorPayload(payload)
    if (clientErrors) {
      showErrors(clientErrors)
      return
    }

    setErrors(emptyMonitorFormErrors())
    setIsSubmitting(true)
    const outcome = monitor
      ? await updateMonitor(monitor.id, payload)
      : await createMonitor(payload)
    setIsSubmitting(false)

    if (outcome.type === "success") {
      router.push(monitor ? `/monitors/${monitor.id}` : "/monitors")
      router.refresh()
      return
    }
    showErrors(adaptMonitorFormFailure(outcome, isEditing ? "edit" : "create"))
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Monitor configuration</CardTitle>
        <CardDescription>Configure the endpoint, schedule, and response rules used by this monitor.</CardDescription>
      </CardHeader>
      <form onSubmit={submitMonitor} noValidate>
        <CardContent>
          <FieldGroup>
            {hasErrors ? (
              <Field data-invalid>
                <FieldError
                  ref={errorSummaryRef}
                  id="monitor-error-summary"
                  tabIndex={-1}
                  aria-live="assertive"
                  className="flex flex-col gap-3 rounded-lg border p-4 focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <p className="font-medium">Check the following before submitting again:</p>
                  {errors.fieldErrors.length ? (
                    <ul className="ml-4 flex list-disc flex-col gap-1">
                      {errors.fieldErrors.map((error, index) => {
                        const field = error.field as MonitorInputField
                        return (
                          <li key={`${field}-${index}`}>
                            <a href={`#${FIELD_DETAILS[field].id}`} onClick={(event) => focusField(event, field)}>
                              {FIELD_DETAILS[field].label}: {error.message}
                            </a>
                          </li>
                        )
                      })}
                    </ul>
                  ) : null}
                  {errors.generalErrors.length ? (
                    <div data-testid="monitor-general-errors" className="flex flex-col gap-1">
                      <p className="font-medium">Submission error</p>
                      {errors.generalErrors.map((message) => <p key={message}>{message}</p>)}
                    </div>
                  ) : null}
                </FieldError>
              </Field>
            ) : null}

            <FieldSet>
              <FieldLegend>Endpoint</FieldLegend>
              <FieldDescription id="monitor-endpoint-guidance">
                Use a publicly accessible HTTP or HTTPS URL. Private and local destinations are rejected by the service.
              </FieldDescription>
              <FieldGroup className="grid gap-5 md:grid-cols-2">
                <Field className="md:col-span-2" data-invalid={errorsFor("name").length > 0}>
                  <FieldLabel htmlFor="monitor-name">Name</FieldLabel>
                  <Input
                    id="monitor-name"
                    name="name"
                    maxLength={200}
                    defaultValue={monitor?.name}
                    required
                    aria-invalid={errorsFor("name").length > 0}
                    aria-describedby={describedBy(errors, "name", "monitor-name-guidance")}
                  />
                  <FieldDescription id="monitor-name-guidance">Use a recognizable name for this endpoint.</FieldDescription>
                  <FieldError id={errorId("name")} errors={errorsFor("name")} />
                </Field>
                <Field className="md:col-span-2" data-invalid={errorsFor("url").length > 0}>
                  <FieldLabel htmlFor="monitor-url">URL</FieldLabel>
                  <Input
                    id="monitor-url"
                    name="url"
                    type="url"
                    maxLength={2048}
                    defaultValue={monitor?.url}
                    placeholder="https://example.com/health"
                    required
                    aria-invalid={errorsFor("url").length > 0}
                    aria-describedby={describedBy(errors, "url", "monitor-url-guidance")}
                  />
                  <FieldDescription id="monitor-url-guidance">Only basic URL syntax is checked here; the service validates the destination.</FieldDescription>
                  <FieldError id={errorId("url")} errors={errorsFor("url")} />
                </Field>
                <Field data-invalid={errorsFor("http_method").length > 0}>
                  <FieldLabel htmlFor="monitor-method">HTTP method</FieldLabel>
                  <select
                    id="monitor-method"
                    name="http_method"
                    defaultValue={monitor?.http_method ?? "GET"}
                    required
                    aria-invalid={errorsFor("http_method").length > 0}
                    aria-describedby={describedBy(errors, "http_method", "monitor-method-guidance")}
                    className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                  >
                    <option value="GET">GET</option>
                    <option value="HEAD">HEAD</option>
                  </select>
                  <FieldDescription id="monitor-method-guidance">GET reads the endpoint response; HEAD requests headers only.</FieldDescription>
                  <FieldError id={errorId("http_method")} errors={errorsFor("http_method")} />
                </Field>
              </FieldGroup>
            </FieldSet>

            <FieldSet>
              <FieldLegend>Schedule</FieldLegend>
              <FieldDescription>Choose how often a check may run and how long it may wait for a response.</FieldDescription>
              <FieldGroup className="grid gap-5 md:grid-cols-2">
                <Field data-invalid={errorsFor("interval_seconds").length > 0}>
                  <FieldLabel htmlFor="monitor-interval">Interval (seconds)</FieldLabel>
                  <Input
                    id="monitor-interval"
                    name="interval_seconds"
                    type="number"
                    min={1}
                    max={86400}
                    step={1}
                    defaultValue={monitor?.interval_seconds ?? 60}
                    required
                    aria-invalid={errorsFor("interval_seconds").length > 0}
                    aria-describedby={describedBy(errors, "interval_seconds", "monitor-interval-guidance")}
                  />
                  <FieldDescription id="monitor-interval-guidance">Between 1 second and 24 hours.</FieldDescription>
                  <FieldError id={errorId("interval_seconds")} errors={errorsFor("interval_seconds")} />
                </Field>
                <Field data-invalid={errorsFor("timeout_seconds").length > 0}>
                  <FieldLabel htmlFor="monitor-timeout">Timeout (seconds)</FieldLabel>
                  <Input
                    id="monitor-timeout"
                    name="timeout_seconds"
                    type="number"
                    min={1}
                    max={300}
                    step={1}
                    defaultValue={monitor?.timeout_seconds ?? 10}
                    required
                    aria-invalid={errorsFor("timeout_seconds").length > 0}
                    aria-describedby={describedBy(errors, "timeout_seconds", "monitor-timeout-guidance")}
                  />
                  <FieldDescription id="monitor-timeout-guidance">Between 1 second and 5 minutes.</FieldDescription>
                  <FieldError id={errorId("timeout_seconds")} errors={errorsFor("timeout_seconds")} />
                </Field>
              </FieldGroup>
            </FieldSet>

            <FieldSet>
              <FieldLegend>Success Criteria</FieldLegend>
              <FieldDescription>Define accepted status codes and the consecutive results needed to change state.</FieldDescription>
              <FieldGroup className="grid gap-5 md:grid-cols-2">
                <Field data-invalid={errorsFor("expected_status_min").length > 0}>
                  <FieldLabel htmlFor="monitor-status-min">Minimum accepted status</FieldLabel>
                  <Input
                    id="monitor-status-min"
                    name="expected_status_min"
                    type="number"
                    min={100}
                    max={599}
                    step={1}
                    defaultValue={monitor?.expected_status_min ?? 200}
                    required
                    aria-invalid={errorsFor("expected_status_min").length > 0}
                    aria-describedby={describedBy(errors, "expected_status_min", "monitor-status-min-guidance")}
                  />
                  <FieldDescription id="monitor-status-min-guidance">Lowest HTTP status code considered successful.</FieldDescription>
                  <FieldError id={errorId("expected_status_min")} errors={errorsFor("expected_status_min")} />
                </Field>
                <Field data-invalid={errorsFor("expected_status_max").length > 0}>
                  <FieldLabel htmlFor="monitor-status-max">Maximum accepted status</FieldLabel>
                  <Input
                    id="monitor-status-max"
                    name="expected_status_max"
                    type="number"
                    min={100}
                    max={599}
                    step={1}
                    defaultValue={monitor?.expected_status_max ?? 399}
                    required
                    aria-invalid={errorsFor("expected_status_max").length > 0}
                    aria-describedby={describedBy(errors, "expected_status_max", "monitor-status-max-guidance")}
                  />
                  <FieldDescription id="monitor-status-max-guidance">Highest HTTP status code considered successful.</FieldDescription>
                  <FieldError id={errorId("expected_status_max")} errors={errorsFor("expected_status_max")} />
                </Field>
                <Field data-invalid={errorsFor("failure_threshold").length > 0}>
                  <FieldLabel htmlFor="monitor-failure-threshold">Failure threshold</FieldLabel>
                  <Input
                    id="monitor-failure-threshold"
                    name="failure_threshold"
                    type="number"
                    min={1}
                    max={100}
                    step={1}
                    defaultValue={monitor?.failure_threshold ?? 3}
                    required
                    aria-invalid={errorsFor("failure_threshold").length > 0}
                    aria-describedby={describedBy(errors, "failure_threshold", "monitor-failure-guidance")}
                  />
                  <FieldDescription id="monitor-failure-guidance">Consecutive failed results required before a future state change.</FieldDescription>
                  <FieldError id={errorId("failure_threshold")} errors={errorsFor("failure_threshold")} />
                </Field>
                <Field data-invalid={errorsFor("recovery_threshold").length > 0}>
                  <FieldLabel htmlFor="monitor-recovery-threshold">Recovery threshold</FieldLabel>
                  <Input
                    id="monitor-recovery-threshold"
                    name="recovery_threshold"
                    type="number"
                    min={1}
                    max={100}
                    step={1}
                    defaultValue={monitor?.recovery_threshold ?? 2}
                    required
                    aria-invalid={errorsFor("recovery_threshold").length > 0}
                    aria-describedby={describedBy(errors, "recovery_threshold", "monitor-recovery-guidance")}
                  />
                  <FieldDescription id="monitor-recovery-guidance">Consecutive successful results required before a future recovery.</FieldDescription>
                  <FieldError id={errorId("recovery_threshold")} errors={errorsFor("recovery_threshold")} />
                </Field>
              </FieldGroup>
            </FieldSet>
          </FieldGroup>
        </CardContent>
        <CardFooter className="mt-6 justify-end pt-6">
          <Button type="submit" size="lg" disabled={isSubmitting}>
            {isSubmitting ? <Loader2Icon className="animate-spin" data-icon="inline-start" /> : null}
            {isSubmitting
              ? `${isEditing ? "Saving changes" : "Creating monitor"}…`
              : isEditing ? "Save changes" : "Create monitor"}
          </Button>
        </CardFooter>
      </form>
    </Card>
  )
}
