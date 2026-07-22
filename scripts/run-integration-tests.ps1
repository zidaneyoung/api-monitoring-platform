param(
    [string]$PytestArgs = ""
)

$ErrorActionPreference = "Stop"

$ProjectName = "api-monitoring-integration-tests"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $RepositoryRoot "compose.integration.yaml"
$TestExitCode = 1
$PreviousPytestArgs = $env:PYTEST_ARGS

try {
    $env:PYTEST_ARGS = $PytestArgs
    & docker compose --project-name $ProjectName --file $ComposeFile up `
        --build `
        --abort-on-container-exit `
        --exit-code-from tests
    $TestExitCode = $LASTEXITCODE
}
finally {
    & docker compose --project-name $ProjectName --file $ComposeFile down `
        --volumes `
        --remove-orphans
    if ($LASTEXITCODE -ne 0 -and $TestExitCode -eq 0) {
        $TestExitCode = $LASTEXITCODE
    }
    if ($null -eq $PreviousPytestArgs) {
        Remove-Item Env:PYTEST_ARGS -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTEST_ARGS = $PreviousPytestArgs
    }
}

exit $TestExitCode
