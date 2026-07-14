import type { Metadata } from "next"
import "./globals.css"
import { Geist } from "next/font/google"
import { AppShell } from "@/components/app-shell"
import { cn } from "@/lib/utils"

const geist = Geist({ subsets: ["latin"], variable: "--font-geist-sans" })

const themeScript = `try{const t=localStorage.getItem("theme");document.documentElement.classList.toggle("dark",t==="dark"||(!t&&matchMedia("(prefers-color-scheme: dark)").matches))}catch{}`

export const metadata: Metadata = {
  title: "API Monitoring Platform",
  description: "Monitor API and website availability.",
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={cn("font-sans", geist.variable)} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  )
}
