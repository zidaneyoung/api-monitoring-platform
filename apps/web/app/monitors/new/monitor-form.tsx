"use client"

import { useRouter } from "next/navigation"
import { Loader2Icon } from "lucide-react"
import { useState, type FormEvent } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  createMonitor,
  type MonitorCreatePayload,
  type MonitorError,
  type MonitorField,
} from "@/lib/monitor-api"


const initialErrors: MonitorError[] = []

function numberValue(formData: FormData, field: MonitorField): number {
  return Number(formData.get(field))
}

function outcomeMessage(type: string): string {
  if (type === "unauthenticated") return "Your session has expired. Sign in and try again."
  if (type === "unavailable") return "Monitor storage is temporarily unavailable. Try again."
  if (type === "timeout") return "The request timed out. Try again."
  if (type === "network_error") return "Unable to reach the service. Check your connection and try again."
  return "The monitor could not be created. Try again."
}

export function MonitorForm() {
  const router = useRouter()
  const [errors, setErrors] = useState<MonitorError[]>(initialErrors)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const errorFor = (field: MonitorField) => errors.find((error) => error.field === field)

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

    setErrors(initialErrors)
    setIsSubmitting(true)
    const outcome = await createMonitor(payload)
    setIsSubmitting(false)

    if (outcome.type === "success") {
      router.push("/monitors")
      router.refresh()
      return
    }
    setErrors(outcome.type === "validation"
      ? outcome.errors
      : [{ field: "form", message: outcomeMessage(outcome.type) }])
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Monitor configuration</CardTitle>
        <CardDescription>All fields are validated before the monitor is scheduled.</CardDescription>
      </CardHeader>
      <form onSubmit={submitMonitor} noValidate>
        <CardContent>
          <FieldGroup className="grid gap-5 md:grid-cols-2">
            <Field className="md:col-span-2" data-invalid={Boolean(errorFor("name"))}>
              <FieldLabel htmlFor="monitor-name">Name</FieldLabel>
              <Input id="monitor-name" name="name" maxLength={200} required aria-invalid={Boolean(errorFor("name"))} />
              <FieldError>{errorFor("name")?.message}</FieldError>
            </Field>
            <Field className="md:col-span-2" data-invalid={Boolean(errorFor("url"))}>
              <FieldLabel htmlFor="monitor-url">URL</FieldLabel>
              <Input id="monitor-url" name="url" type="url" maxLength={2048} placeholder="https://example.com/health" required aria-invalid={Boolean(errorFor("url"))} />
              <FieldError>{errorFor("url")?.message}</FieldError>
            </Field>
            <Field data-invalid={Boolean(errorFor("http_method"))}>
              <FieldLabel htmlFor="monitor-method">HTTP method</FieldLabel>
              <select id="monitor-method" name="http_method" defaultValue="GET" aria-invalid={Boolean(errorFor("http_method"))} className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50">
                <option value="GET">GET</option>
                <option value="HEAD">HEAD</option>
              </select>
              <FieldError>{errorFor("http_method")?.message}</FieldError>
            </Field>
            <Field data-invalid={Boolean(errorFor("interval_seconds"))}>
              <FieldLabel htmlFor="monitor-interval">Interval (seconds)</FieldLabel>
              <Input id="monitor-interval" name="interval_seconds" type="number" min={1} max={86400} defaultValue={60} required aria-invalid={Boolean(errorFor("interval_seconds"))} />
              <FieldError>{errorFor("interval_seconds")?.message}</FieldError>
            </Field>
            <Field data-invalid={Boolean(errorFor("timeout_seconds"))}>
              <FieldLabel htmlFor="monitor-timeout">Timeout (seconds)</FieldLabel>
              <Input id="monitor-timeout" name="timeout_seconds" type="number" min={1} max={300} defaultValue={10} required aria-invalid={Boolean(errorFor("timeout_seconds"))} />
              <FieldError>{errorFor("timeout_seconds")?.message}</FieldError>
            </Field>
            <Field data-invalid={Boolean(errorFor("failure_threshold"))}>
              <FieldLabel htmlFor="monitor-failure-threshold">Failure threshold</FieldLabel>
              <Input id="monitor-failure-threshold" name="failure_threshold" type="number" min={1} max={100} defaultValue={3} required aria-invalid={Boolean(errorFor("failure_threshold"))} />
              <FieldError>{errorFor("failure_threshold")?.message}</FieldError>
            </Field>
            <Field data-invalid={Boolean(errorFor("recovery_threshold"))}>
              <FieldLabel htmlFor="monitor-recovery-threshold">Recovery threshold</FieldLabel>
              <Input id="monitor-recovery-threshold" name="recovery_threshold" type="number" min={1} max={100} defaultValue={2} required aria-invalid={Boolean(errorFor("recovery_threshold"))} />
              <FieldError>{errorFor("recovery_threshold")?.message}</FieldError>
            </Field>
            <Field data-invalid={Boolean(errorFor("expected_status_min"))}>
              <FieldLabel htmlFor="monitor-status-min">Minimum accepted status</FieldLabel>
              <Input id="monitor-status-min" name="expected_status_min" type="number" min={100} max={599} defaultValue={200} required aria-invalid={Boolean(errorFor("expected_status_min"))} />
              <FieldError>{errorFor("expected_status_min")?.message}</FieldError>
            </Field>
            <Field data-invalid={Boolean(errorFor("expected_status_max"))}>
              <FieldLabel htmlFor="monitor-status-max">Maximum accepted status</FieldLabel>
              <Input id="monitor-status-max" name="expected_status_max" type="number" min={100} max={599} defaultValue={399} required aria-invalid={Boolean(errorFor("expected_status_max"))} />
              <FieldError>{errorFor("expected_status_max")?.message}</FieldError>
            </Field>
            <Field className="md:col-span-2" data-invalid={Boolean(errorFor("form"))}>
              <FieldError>{errorFor("form")?.message}</FieldError>
            </Field>
          </FieldGroup>
        </CardContent>
        <CardFooter className="mt-6 justify-end border-t pt-6">
          <Button type="submit" size="lg" disabled={isSubmitting}>
            {isSubmitting ? <Loader2Icon className="animate-spin" data-icon="inline-start" /> : null}
            {isSubmitting ? "Creating monitor…" : "Create monitor"}
          </Button>
        </CardFooter>
      </form>
    </Card>
  )
}
