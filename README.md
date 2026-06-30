# api-monitoring-platform

A full-stack API and website monitoring platform with scheduled checks, incident detection, email alerts, uptime analytics, and incident history.

Repository Structure

apps/web

Contains the Next.js frontend application.

apps/backend

Contains the FastAPI backend, Celery workers, and application logic.

infrastructure

Contains Docker, deployment, monitoring, and infrastructure configuration.

docs

Contains product requirements, architecture decisions, and technical documentation.

## Environment Setup

This repository keeps example environment files in source control and keeps local secret files out of Git.

Backend:

```bash
cp apps/backend/.env.example apps/backend/.env
```

Frontend:

```bash
cp apps/web/.env.example apps/web/.env.local
```

Then open both files and replace every placeholder value with your local settings.

Guidelines:

- Backend variables in `apps/backend/.env` are private and should never be exposed to the browser.
- Frontend variables that must be available in the browser must use the `NEXT_PUBLIC_` prefix.
- Do not commit real secrets, passwords, API keys, or tokens.
- Example files such as `.env.example` remain trackable in Git so new developers can copy them into local env files.

