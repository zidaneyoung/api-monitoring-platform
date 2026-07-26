# Container image build and publication

The `Build images` GitHub Actions workflow runs after a successful `Tests`
workflow for a push to `main`. It can also be run manually. The workflow builds
the production frontend and backend images before any registry login or
publication step, so a failed build cannot publish either image.

The backend image is shared by the API, monitor worker, notification worker,
and scheduler. The workflow verifies the non-root runtime and Celery
entrypoint after building it.

## Tagging policy

Every image uses the complete validated Git commit SHA as its immutable tag:

```text
REGISTRY/NAMESPACE/api-monitoring-frontend:GIT_SHA
REGISTRY/NAMESPACE/api-monitoring-backend:GIT_SHA
```

For example, `registry.example.invalid/team/api-monitoring-backend:abc123...`.
OCI labels record the same revision and the source repository. GitHub Actions
cache scopes are separate for the frontend and backend.

## Optional publication

Build-only operation requires no registry configuration. Publication remains
disabled until one registry is deliberately selected and all of the following
repository configuration exists:

| Kind | Name | Purpose |
| --- | --- | --- |
| Variable | `PUBLISH_CONTAINER_IMAGES` | Set to `true` for publication after successful `main` validation |
| Variable | `CONTAINER_REGISTRY` | Hostname of the one selected OCI registry |
| Variable | `CONTAINER_IMAGE_NAMESPACE` | Account or namespace below that registry |
| Variable | `PRODUCTION_PUBLIC_API_URL` | Public API URL embedded in the frontend image |
| Secret | `CONTAINER_REGISTRY_USERNAME` | Registry login identity |
| Secret | `CONTAINER_REGISTRY_PASSWORD` | Registry token or password |

A manual run with `publish` enabled performs the same validation and fails
closed when any required value is missing. Secret values are passed only to
the registry login action and are never echoed.

After publication, the workflow removes its local registry tags, pulls both
immutable references, and starts their health endpoints. This verifies that
the published artifacts can be retrieved and run. Registry selection,
credentials, and enabling publication are external release prerequisites; the
repository intentionally supplies no guessed provider or secret values.
