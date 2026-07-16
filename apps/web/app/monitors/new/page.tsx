import Link from "next/link"
import { ArrowLeftIcon } from "lucide-react"

import { buttonVariants } from "@/components/ui/button"

import { MonitorForm } from "./monitor-form"


export default function NewMonitorPage() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-5 px-4 py-8 sm:px-6 lg:px-8">
      <Link className={buttonVariants({ variant: "outline" })} href="/monitors">
        <ArrowLeftIcon data-icon="inline-start" />
        Back to monitors
      </Link>
      <header>
        <h1 className="text-[2.25rem] font-semibold tracking-[-0.045em] sm:text-[2.6rem]">
          Create monitor
        </h1>
        <p className="mt-1 text-muted-foreground">
          Configure an HTTP endpoint and its expected response behavior.
        </p>
      </header>
      <MonitorForm />
    </main>
  )
}
