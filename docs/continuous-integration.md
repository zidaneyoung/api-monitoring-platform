# Continuous integration

The `Tests` GitHub Actions workflow runs for every pull request and every push
to `main`. A newer run for the same ref cancels an older in-progress run.
Repository contents are read-only and the workflow does not consume deployment
secrets.

The workflow contains four independent required validation jobs:

- `Formatting` rejects whitespace errors introduced by the change.
- `Frontend validation` installs the locked npm graph, runs ESLint, checks
  TypeScript, and runs the Vitest unit suite.
- `Backend validation` installs the pinned development requirements, runs
  Ruff's Python correctness checks, compiles the Python source, and runs the
  pytest unit suite.
- `PostgreSQL and Redis integration` creates isolated PostgreSQL, Redis, and
  Mailpit containers, applies migrations, runs the integration suite, and
  removes its containers and volumes.

The Node and Python caches are keyed from their dependency lock or requirement
files by the official setup actions. Test service credentials are fixed,
non-production values committed in `compose.integration.yaml`; no secret value
is printed or required.

## Local equivalents

From the repository root:

```powershell
git diff --check

Push-Location apps/web
npm ci --no-audit --no-fund
npm run lint
npm run typecheck
npm test
Pop-Location

Push-Location apps/backend
python -m pip install --disable-pip-version-check -r requirements-dev.txt
python -m ruff check --target-version py312 --select F app tests
python -m compileall -q app tests
python -m pytest -q
Pop-Location

./scripts/run-integration-tests.ps1
```

Each command is allowed to return its native exit code. Any non-zero result
fails its GitHub Actions step and therefore fails the workflow.
