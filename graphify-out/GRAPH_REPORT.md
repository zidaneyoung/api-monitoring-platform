# Graph Report - api-monitoring-platform  (2026-07-14)

## Corpus Check
- 51 files · ~18,415 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 331 nodes · 633 edges · 22 communities (18 shown, 4 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `11ee856a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 24|Community 24]]

## God Nodes (most connected - your core abstractions)
1. `cn()` - 77 edges
2. `compilerOptions` - 16 edges
3. `Playwright Interactive Skill` - 15 edges
4. `Button()` - 12 edges
5. `Card()` - 12 edges
6. `CardContent()` - 12 edges
7. `api-monitoring-platform` - 11 edges
8. `buttonVariants` - 10 edges
9. `CardHeader()` - 10 edges
10. `EmptyState()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `AppNavigation()` --calls--> `cn()`  [EXTRACTED]
  apps/web/app/dashboard/page.tsx → apps/web/lib/utils.ts
- `IncidentStatusBadge()` --calls--> `cn()`  [EXTRACTED]
  apps/web/app/monitors/incidents/[incidentId]/page.tsx → apps/web/lib/utils.ts
- `CheckStatusBadge()` --calls--> `cn()`  [EXTRACTED]
  apps/web/app/monitors/incidents/[incidentId]/page.tsx → apps/web/lib/utils.ts
- `IncidentStatusBadge()` --calls--> `cn()`  [EXTRACTED]
  apps/web/app/monitors/incidents/page.tsx → apps/web/lib/utils.ts
- `ApplicationNavigation()` --calls--> `cn()`  [EXTRACTED]
  apps/web/components/app-shell.tsx → apps/web/lib/utils.ts

## Import Cycles
- None detected.

## Communities (22 total, 4 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.12
Nodes (23): MonitorStatus, StatusBadge(), statusDetails, baseChecks, configuration, RecentCheck, mockMonitors, Monitor (+15 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (27): Bootstrap (Run Once), Checklists, Choose Session Mode, Cleanup, Common Failure Modes, Core Workflow, Desktop Web Context, Dev Server (+19 more)

### Community 2 - "Community 2"
Cohesion: 0.12
Nodes (24): geist, metadata, RootLayout(), AppShell(), cn(), SummaryCard(), CardAction(), DialogOverlay() (+16 more)

### Community 3 - "Community 3"
Cohesion: 0.09
Nodes (23): CheckStatusBadge(), formatTime(), IncidentDetailsPage(), IncidentStatusBadge(), normalizeState(), PageProps, timeFormatter, checksForMonitor() (+15 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (21): aliases, components, hooks, lib, ui, utils, iconLibrary, menuAccent (+13 more)

### Community 5 - "Community 5"
Cohesion: 0.10
Nodes (19): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+11 more)

### Community 6 - "Community 6"
Cohesion: 0.11
Nodes (16): ApplicationHeader(), ApplicationNavigation(), isCurrentRoute(), NavigationItem(), navigationItems, AuthForm(), Mode, Tone (+8 more)

### Community 7 - "Community 7"
Cohesion: 0.16
Nodes (12): load_settings(), Settings, probe_postgres(), probe_redis(), _probe_succeeded(), readiness(), Exception, JSONResponse (+4 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (25): ActiveIncidents(), AppNavigation(), DashboardPage(), DashboardState, navigation, normalizeState(), PageProps, responseBars (+17 more)

### Community 9 - "Community 9"
Cohesion: 0.17
Nodes (11): api-monitoring-platform, Clone the repository, Create environment files, Frontend dependency workflow, Migration commands, Notes, Repository structure, Required software (+3 more)

### Community 11 - "Community 11"
Cohesion: 0.15
Nodes (9): formatTime(), IncidentCard(), IncidentStatusBadge(), MonitorsPage(), normalizeState(), PageProps, timeFormatter, Badge() (+1 more)

### Community 18 - "Community 18"
Cohesion: 0.06
Nodes (32): dependencies, @base-ui/react, class-variance-authority, clsx, lucide-react, next, react, react-dom (+24 more)

## Knowledge Gaps
- **129 isolated node(s):** `Mode`, `Tone`, `PageProps`, `DashboardState`, `SummaryMetric` (+124 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `cn()` connect `Community 2` to `Community 0`, `Community 3`, `Community 6`, `Community 8`, `Community 11`?**
  _High betweenness centrality (0.125) - this node is a cross-community bridge._
- **Why does `ThemeToggle()` connect `Community 6` to `Community 8`, `Community 2`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._
- **Why does `Button()` connect `Community 6` to `Community 0`, `Community 2`, `Community 3`, `Community 8`, `Community 11`?**
  _High betweenness centrality (0.006) - this node is a cross-community bridge._
- **What connects `Mode`, `Tone`, `Backend application package.` to the rest of the system?**
  _130 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.12436974789915967 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.07142857142857142 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.12183908045977011 - nodes in this community are weakly interconnected._