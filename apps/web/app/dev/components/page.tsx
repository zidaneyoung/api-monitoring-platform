import { PlusIcon } from "lucide-react"

import { StatusBadge, type MonitorStatus } from "@/components/status-badge"
import { ThemeToggle } from "@/components/theme-toggle"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

const monitors: Array<{ name: string; endpoint: string; status: MonitorStatus }> = [
  { name: "Public API", endpoint: "https://api.example.com/health", status: "up" },
  { name: "Checkout", endpoint: "https://example.com/checkout", status: "down" },
  { name: "Staging", endpoint: "https://staging.example.com", status: "paused" },
]

export default function ComponentsPage() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-8 sm:px-6 lg:px-8">
      <header className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-2">
          <Badge variant="outline">Development</Badge>
          <h1>Component foundations</h1>
          <p className="max-w-2xl text-muted-foreground">Shared typography, spacing, status, form, and data-display patterns.</p>
        </div>
        <ThemeToggle />
      </header>

      <section className="flex flex-col gap-4" aria-labelledby="status-heading">
        <h2 id="status-heading">Monitor status</h2>
        <div className="flex flex-wrap gap-2">
          <StatusBadge status="unknown" />
          <StatusBadge status="up" />
          <StatusBadge status="down" />
          <StatusBadge status="paused" />
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2" aria-label="Component examples">
        <Card>
          <CardHeader>
            <CardTitle>Create monitor</CardTitle>
            <CardDescription>Fields use shared labels, help text, focus states, and spacing.</CardDescription>
          </CardHeader>
          <CardContent>
            <form id="monitor-form">
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="monitor-name">Monitor name</FieldLabel>
                  <Input id="monitor-name" name="name" placeholder="Production API" required />
                </Field>
                <Field>
                  <FieldLabel htmlFor="monitor-url">Endpoint URL</FieldLabel>
                  <Input id="monitor-url" name="url" type="url" placeholder="https://api.example.com/health" required />
                  <FieldDescription>Use a public HTTP or HTTPS endpoint.</FieldDescription>
                </Field>
              </FieldGroup>
            </form>
          </CardContent>
          <CardFooter className="justify-end gap-2">
            <Button variant="outline" type="reset" form="monitor-form">Reset</Button>
            <Button type="submit" form="monitor-form">Create monitor</Button>
          </CardFooter>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Actions and dialog</CardTitle>
            <CardDescription>Common button variants and an accessible titled dialog.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button>Primary</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="destructive">Destructive</Button>
          </CardContent>
          <CardFooter>
            <Dialog>
              <DialogTrigger render={<Button variant="outline" />}>
                <PlusIcon data-icon="inline-start" />
                Open dialog
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add endpoint</DialogTitle>
                  <DialogDescription>Enter endpoint details. No data is submitted from this development page.</DialogDescription>
                </DialogHeader>
                <Field>
                  <FieldLabel htmlFor="dialog-url">Endpoint URL</FieldLabel>
                  <Input id="dialog-url" type="url" placeholder="https://example.com/health" />
                </Field>
                <DialogFooter showCloseButton>
                  <Button>Create</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </CardFooter>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Monitor table</CardTitle>
          <CardDescription>Responsive shared table primitives with explicit status labels.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableCaption>Example data only. No backend integration.</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>Monitor</TableHead>
                <TableHead>Endpoint</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {monitors.map((monitor) => (
                <TableRow key={monitor.name}>
                  <TableCell className="font-medium">{monitor.name}</TableCell>
                  <TableCell>{monitor.endpoint}</TableCell>
                  <TableCell><StatusBadge status={monitor.status} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </main>
  )
}
