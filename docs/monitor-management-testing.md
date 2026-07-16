# Monitor management manual testing

This matrix covers the persisted monitor-management workflow only. It does not
verify scheduled execution, HTTP checks, automatic health transitions, check
history, incidents, notifications, or analytics.

## Prerequisites

1. Start the local stack with docker compose up -d --build.
2. Apply migrations with docker compose exec backend alembic upgrade head.
3. Open http://localhost:3000 and register or sign in.
4. Use a public destination such as https://example.com/ for successful
   creation. Private, loopback, localhost, and metadata destinations are
   intentionally rejected.

## Test matrix

| Path | Steps | Expected result |
| --- | --- | --- |
| Create validation | Open /monitors/new, enter a name and http://localhost:3000, then submit. | The URL field is marked invalid, exposes aria-invalid=true, displays the public-destination message, leaves other valid fields unmarked, and preserves entered values. |
| Create | Replace the URL with https://example.com/ and submit. | One monitor is created with Unknown status and the browser returns to /monitors. |
| List | Open /monitors after creating a monitor. | Only the signed-in user's monitors appear. Unknown and Paused states render correctly and pagination controls remain usable. |
| List context | Change rows per page, refresh, open a monitor, then return from details and edit. | The canonical page and page-size URL survives refresh and the previous list URL is restored. Invalid values fall back to page 1 and 10 rows. |
| Details | Select the monitor name from the list. | Current state, endpoint, schedule, success criteria, and actions are separate. No deferred check-history data is invented. An unknown identifier produces the controlled not-found state. |
| Endpoint utilities | On details, choose Copy endpoint and inspect Open endpoint. | Copy success or failure is visible. Open endpoint uses a safe new tab and does not run an application-side network check. |
| Edit validation | Open Edit, enter http://localhost:3000, and save. | The URL field receives the same field-specific validation as Create and all edited values remain present. |
| Edit | Enter a public URL, change configuration, and save. | The existing monitor is updated without changing its identity or history relationships, then details show the persisted values. |
| Unsaved edit | Change a value, choose an internal navigation link, cancel once, then discard. Repeat after reverting the value or saving. | Dirty edits produce a focus-contained warning and retain values when cancelled. Reverted or saved forms do not warn. Refresh or tab close uses the browser's native warning where supported. |
| Pause | Choose Pause and cancel once, then confirm. | Cancellation sends no request. Confirmation persists Paused state, disables future scheduling, and clears next_check_at. |
| Resume | Choose Resume for the paused monitor. | The monitor returns to Unknown, becomes enabled, and receives one future next_check_at. Repeating Resume remains safe. |
| Delete | Choose Delete and cancel once, then confirm. | Cancellation preserves the monitor. Confirmation hard-deletes it and removes it from the list or returns to the list from details. |
| Ownership | Sign in as a different user and try the first user's monitor URL or API identifier. | The monitor is not disclosed or mutated. |

## Regression commands

From apps/web, the focused Stage 4 suite is:

~~~text
npm test -- lib/monitor-api.test.ts lib/monitor-form-errors.test.ts lib/monitor-navigation.test.ts lib/monitor-time.test.ts components/status-badge.test.tsx app/monitors/new/monitor-form.test.tsx app/monitors/monitor-list.test.tsx app/monitors/monitor-pause-button.test.tsx app/monitors/monitor-delete-button.test.tsx app/monitors/[monitorId]/monitor-details.test.tsx app/monitors/[monitorId]/edit/monitor-edit.test.tsx
npm run lint
npm run typecheck
~~~

From apps/backend:

~~~text
python -m pytest -q tests/test_monitors_api.py tests/test_monitor_urls.py tests/test_monitor_destinations.py
~~~

## Automated coverage

| Behavior | Coverage |
| --- | --- |
| Invalid and successful create/edit | Monitor API and shared form component tests |
| Pause/resume confirmation, completion, duplicate prevention, and failure | State-button and details component tests |
| Delete cancellation, completion, duplicate prevention, and failure | Delete-button, list, and details component tests |
| Pagination and return navigation | Navigation helper and list/details/edit component tests |
| Unsaved edit warnings | Shared form component tests |
| Ownership isolation and repeated mutation safety | Backend monitor API integration tests |
| Stale read and mutation responses | List, details, form, pause, and delete component tests |
| UTC timestamp conversion and invalid values | Timestamp helper and list component tests |

## E2E and CI alignment

These focused tests are the monitor-management subset of
[issue #79](https://github.com/zidaneyoung/api-monitoring-platform/issues/79).
They do not close that issue because its full browser journey requires the
deferred scheduler, health-transition, incident, recovery, dashboard, and
history work.

The repository does not yet have the deterministic E2E environment or base
GitHub Actions test/build workflows tracked by
[issue #83](https://github.com/zidaneyoung/api-monitoring-platform/issues/83)
and [issue #84](https://github.com/zidaneyoung/api-monitoring-platform/issues/84).
A monitor-management Playwright job should be added with isolated data and
failure artifacts when those prerequisites exist; this Stage 4 pass does not
silently expand either CI issue or introduce a partial full-MVP workflow.
