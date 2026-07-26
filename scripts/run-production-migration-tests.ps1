$ErrorActionPreference = "Stop"

$ProjectName = "api-monitoring-production-migration-tests"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $RepositoryRoot "compose.migrations.yaml"
$TestExitCode = 1

try {
    & docker compose --project-name $ProjectName --file $ComposeFile up `
        --detach `
        --wait `
        db
    if ($LASTEXITCODE -ne 0) {
        throw "Migration test database failed to start."
    }

    & docker compose --project-name $ProjectName --file $ComposeFile run `
        --rm `
        --no-TTY `
        --build `
        migrate
    if ($LASTEXITCODE -ne 0) {
        throw "Clean production-image migration failed."
    }

    & docker compose --project-name $ProjectName --file $ComposeFile run `
        --rm `
        --no-TTY `
        migrate `
        python -m app.production_migrations current
    if ($LASTEXITCODE -ne 0) {
        throw "Production-image revision inspection failed."
    }

    & docker compose --project-name $ProjectName --file $ComposeFile run `
        --rm `
        --no-TTY `
        migrate
    if ($LASTEXITCODE -ne 0) {
        throw "Repeated production-image migration failed."
    }

    & docker compose --project-name $ProjectName --file $ComposeFile run `
        --rm `
        --no-TTY `
        --build `
        tests
    $TestExitCode = $LASTEXITCODE
}
finally {
    & docker compose --project-name $ProjectName --file $ComposeFile down `
        --volumes `
        --remove-orphans
    if ($LASTEXITCODE -ne 0 -and $TestExitCode -eq 0) {
        $TestExitCode = $LASTEXITCODE
    }
}

exit $TestExitCode
