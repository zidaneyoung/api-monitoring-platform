$ErrorActionPreference = "Stop"

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$IntegrationRunner = Join-Path $RepositoryRoot "scripts/run-integration-tests.ps1"
$ConcurrencyTests = @(
    "tests/test_monitor_scheduler.py"
    "tests/test_monitor_worker.py"
    "tests/test_email_deduplication.py"
) -join " "

& $IntegrationRunner -PytestArgs $ConcurrencyTests
exit $LASTEXITCODE
