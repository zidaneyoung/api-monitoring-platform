import Link from "next/link";
import { ArrowLeft, Clock3, ShieldAlert, ShieldCheck } from "lucide-react";

import { getIncidentById } from "../../incidents-data";

type PageProps = {
  params: Promise<{
    incidentId: string;
  }>;
};

const timeFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "full",
  timeStyle: "short",
  timeZone: "UTC",
});

function formatTime(value: string) {
  return timeFormatter.format(new Date(value));
}

export default async function IncidentDetailsPage({ params }: PageProps) {
  const resolvedParams = await params;
  const incident = getIncidentById(resolvedParams.incidentId);

  if (!incident) {
    return (
      <main className="min-h-screen bg-slate-950 px-4 py-10 text-slate-100 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl rounded-[2rem] border border-white/10 bg-white/5 p-8 shadow-2xl shadow-black/20">
          <p className="text-sm uppercase tracking-[0.24em] text-slate-400">Incident details</p>
          <h1 className="mt-3 text-3xl font-semibold text-white">Incident not found</h1>
          <p className="mt-3 text-sm leading-6 text-slate-400">
            The requested mock incident does not exist in this dataset.
          </p>
          <Link
            href="/monitors"
            className="mt-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white transition hover:border-white/20 hover:bg-white/10"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to incident history
          </Link>
        </div>
      </main>
    );
  }

  const isOpen = incident.section === "open";

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(34,197,94,0.12),_transparent_28%),radial-gradient(circle_at_bottom_left,_rgba(244,63,94,0.12),_transparent_26%),linear-gradient(180deg,_#020617_0%,_#0f172a_100%)] px-4 py-8 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-5xl">
        <Link
          href="/monitors"
          className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200 transition hover:border-white/20 hover:bg-white/10"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to incident history
        </Link>

        <section className="mt-6 rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/20 backdrop-blur sm:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs uppercase tracking-[0.22em] text-slate-300">
                <ShieldAlert className="h-3.5 w-3.5" />
                {incident.monitorName}
              </p>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                {incident.title}
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">{incident.summary}</p>
            </div>
            <span
              className={`inline-flex items-center rounded-full border px-3 py-1 text-sm font-medium ${
                isOpen
                  ? "border-rose-500/30 bg-rose-500/10 text-rose-200"
                  : "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
              }`}
            >
              {incident.status}
            </span>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-3xl border border-white/10 bg-slate-950/50 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Monitor</p>
              <p className="mt-2 text-lg font-semibold text-white">{incident.monitorName}</p>
            </div>
            <div className="rounded-3xl border border-white/10 bg-slate-950/50 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Opened</p>
              <p className="mt-2 text-lg font-semibold text-white">{formatTime(incident.openedAt)}</p>
            </div>
            <div className="rounded-3xl border border-white/10 bg-slate-950/50 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Duration</p>
              <p className="mt-2 flex items-center gap-2 text-lg font-semibold text-white">
                <Clock3 className="h-4 w-4 text-slate-300" />
                {incident.duration}
              </p>
            </div>
            <div className="rounded-3xl border border-white/10 bg-slate-950/50 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Status</p>
              <p className="mt-2 text-lg font-semibold text-white">{incident.status}</p>
            </div>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div className="rounded-3xl border border-white/10 bg-slate-950/50 p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-slate-200">
                {isOpen ? <ShieldAlert className="h-4 w-4 text-rose-300" /> : <ShieldCheck className="h-4 w-4 text-emerald-300" />}
                {isOpen ? "Incident still open" : "Incident resolved"}
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                {isOpen
                  ? "Resolution time is not available yet. The item stays in the open section until it resolves."
                  : `Resolved at ${formatTime(incident.resolvedAt ?? incident.openedAt)}.`}
              </p>
            </div>

            <div className="rounded-3xl border border-white/10 bg-slate-950/50 p-4">
              <p className="text-sm font-medium text-slate-200">Incident ID</p>
              <p className="mt-2 font-mono text-sm text-slate-400">{incident.id}</p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
