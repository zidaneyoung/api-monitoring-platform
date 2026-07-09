import Link from "next/link";
import { AlertTriangle, ChevronLeft, ChevronRight, Clock3, ListChecks, ShieldAlert, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

import { getIncidents } from "./incidents-data";
import type { IncidentRecord } from "./incidents-data";

type PageProps = {
  searchParams?: Promise<{
    state?: string;
  }>;
};

const timeFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

function formatTime(value: string) {
  return timeFormatter.format(new Date(value));
}

function normalizeState(value: string | string[] | undefined) {
  const state = Array.isArray(value) ? value[0] : value;
  if (state === "loading" || state === "empty" || state === "error") {
    return state;
  }
  return "ready";
}

function StatusBadge({ status, tone }: { status: string; tone: "open" | "resolved" }) {
  const style =
    tone === "open"
      ? "border-rose-500/30 bg-rose-500/10 text-rose-200"
      : "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";

  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${style}`}>
      {status}
    </span>
  );
}

function SectionHeader({
  title,
  count,
  tone,
  icon,
}: {
  title: string;
  count: number;
  tone: "open" | "resolved";
  icon: ReactNode;
}) {
  const accent = tone === "open" ? "text-rose-300" : "text-emerald-300";

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        <div className={`flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/5 ${accent}`}>
          {icon}
        </div>
        <div>
          <h2 className="text-lg font-semibold text-white">{title}</h2>
          <p className="text-sm text-slate-400">{count} incidents</p>
        </div>
      </div>
      <span className={`rounded-full border px-3 py-1 text-xs font-medium ${tone === "open" ? "border-rose-500/30 bg-rose-500/10 text-rose-200" : "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"}`}>
        {tone === "open" ? "Active" : "Closed"}
      </span>
    </div>
  );
}

function PaginationPlaceholder() {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3">
      <button
        type="button"
        disabled
        className="inline-flex items-center gap-2 rounded-full border border-white/10 px-3 py-2 text-sm text-slate-500"
      >
        <ChevronLeft className="h-4 w-4" />
        Prev
      </button>
      <p className="text-sm text-slate-400">Page 1 of 3</p>
      <button
        type="button"
        disabled
        className="inline-flex items-center gap-2 rounded-full border border-white/10 px-3 py-2 text-sm text-slate-500"
      >
        Next
        <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  );
}

function IncidentCard({
  incident,
}: {
  incident: IncidentRecord;
}) {
  const isOpen = incident.section === "open";

  return (
    <Link
      href={`/monitors/incidents/${incident.id}`}
      className={`group block rounded-3xl border p-5 transition duration-200 hover:-translate-y-0.5 hover:border-white/20 hover:shadow-2xl hover:shadow-black/20 ${
        isOpen
          ? "border-rose-500/20 bg-gradient-to-br from-rose-500/10 via-slate-950 to-slate-950"
          : "border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 via-slate-950 to-slate-950"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-slate-400">{incident.monitorName}</p>
          <h3 className="mt-2 text-base font-semibold text-white group-hover:text-white/95">{incident.title}</h3>
        </div>
        <StatusBadge status={incident.status} tone={incident.section} />
      </div>

      <div className="mt-5 grid gap-3 text-sm text-slate-300 sm:grid-cols-2">
        <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Opened</p>
          <p className="mt-1 font-medium text-white">{formatTime(incident.openedAt)}</p>
        </div>
        {incident.resolvedAt ? (
          <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Resolved</p>
            <p className="mt-1 font-medium text-white">{formatTime(incident.resolvedAt)}</p>
          </div>
        ) : (
          <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Resolution</p>
            <p className="mt-1 font-medium text-white">Still open</p>
          </div>
        )}
        <div className="rounded-2xl border border-white/8 bg-white/5 p-3 sm:col-span-2">
          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-slate-500">
            <Clock3 className="h-3.5 w-3.5" />
            Duration
          </div>
          <p className="mt-1 font-medium text-white">{incident.duration}</p>
        </div>
      </div>

      <p className="mt-4 text-sm leading-6 text-slate-400">{incident.summary}</p>
    </Link>
  );
}

function SectionList({
  title,
  tone,
  icon,
  incidents,
}: {
  title: string;
  tone: "open" | "resolved";
  icon: ReactNode;
  incidents: IncidentRecord[];
}) {
  return (
    <section className="rounded-[2rem] border border-white/10 bg-white/5 p-4 shadow-2xl shadow-black/20 backdrop-blur xl:p-6">
      <SectionHeader title={title} count={incidents.length} tone={tone} icon={icon} />
      <div className="mt-5 space-y-4">
        {incidents.map((incident) => (
          <IncidentCard key={incident.id} incident={incident} />
        ))}
      </div>
      <div className="mt-5">
        <PaginationPlaceholder />
      </div>
    </section>
  );
}

function LoadingState() {
  return (
    <div className="rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/20">
      <div className="h-8 w-56 rounded-full bg-white/10" />
      <div className="mt-3 h-4 w-80 max-w-full rounded-full bg-white/10" />
      <div className="mt-8 grid gap-5 xl:grid-cols-2">
        {Array.from({ length: 2 }).map((_, index) => (
          <div key={index} className="rounded-3xl border border-white/10 bg-slate-950/50 p-5">
            <div className="h-5 w-40 rounded-full bg-white/10" />
            <div className="mt-5 space-y-3">
              <div className="h-32 rounded-3xl bg-white/5" />
              <div className="h-32 rounded-3xl bg-white/5" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-[2rem] border border-dashed border-white/15 bg-white/5 p-10 text-center shadow-2xl shadow-black/20">
      <ListChecks className="mx-auto h-10 w-10 text-slate-300" />
      <h2 className="mt-4 text-2xl font-semibold text-white">No incidents yet</h2>
      <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-slate-400">
        Mock feed is empty right now. Once incidents exist, open and resolved sections show up here.
      </p>
    </div>
  );
}

function ErrorState() {
  return (
    <div className="rounded-[2rem] border border-rose-500/20 bg-rose-500/10 p-10 shadow-2xl shadow-black/20">
      <AlertTriangle className="h-10 w-10 text-rose-200" />
      <h2 className="mt-4 text-2xl font-semibold text-white">Incident history unavailable</h2>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-rose-100/80">
        Mock data render failed. This state exists for future API wiring and layout QA.
      </p>
    </div>
  );
}

export default async function MonitorsPage({ searchParams }: PageProps) {
  const resolvedSearchParams = (await searchParams) ?? {};
  const state = normalizeState(resolvedSearchParams.state);
  const openIncidents = getIncidents("open");
  const resolvedIncidents = getIncidents("resolved");

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(34,197,94,0.14),_transparent_32%),radial-gradient(circle_at_bottom_right,_rgba(244,63,94,0.12),_transparent_26%),linear-gradient(180deg,_#020617_0%,_#0f172a_100%)] px-4 py-8 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <header className="rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/20 backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <p className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs uppercase tracking-[0.22em] text-slate-300">
                <ShieldAlert className="h-3.5 w-3.5" />
                Incident history
              </p>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                Open and resolved incidents
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">
                Track active incidents, review resolved ones, and jump into detail views from one responsive list.
              </p>
            </div>
            <div className="grid gap-3 text-sm sm:grid-cols-2">
              <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3">
                <p className="text-slate-400">Open</p>
                <p className="mt-1 text-2xl font-semibold text-white">{openIncidents.length}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3">
                <p className="text-slate-400">Resolved</p>
                <p className="mt-1 text-2xl font-semibold text-white">{resolvedIncidents.length}</p>
              </div>
            </div>
          </div>
        </header>

        {state === "loading" ? (
          <LoadingState />
        ) : state === "error" ? (
          <ErrorState />
        ) : state === "empty" ? (
          <EmptyState />
        ) : (
          <div className="grid gap-6 xl:grid-cols-2">
            <SectionList
              title="Open incidents"
              tone="open"
              icon={<ShieldAlert className="h-5 w-5" />}
              incidents={openIncidents}
            />
            <SectionList
              title="Resolved incidents"
              tone="resolved"
              icon={<ShieldCheck className="h-5 w-5" />}
              incidents={resolvedIncidents}
            />
          </div>
        )}
      </div>
    </main>
  );
}
