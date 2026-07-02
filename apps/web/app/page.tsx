import Link from "next/link"

import { buttonVariants } from "@/components/ui/button"

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-6 px-6">
      <h1>API Monitoring Platform</h1>
      <p className="text-muted-foreground">Shared frontend foundations are available on the component development page.</p>
      <Link className={buttonVariants({ className: "w-fit" })} href="/dev/components">View components</Link>
    </main>
  )
}
