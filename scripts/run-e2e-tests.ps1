param(
    [switch]$Headed,
    [string]$Grep
)

$ErrorActionPreference = "Stop"

$ProjectName = "api-monitoring-e2e-tests"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $RepositoryRoot "compose.e2e.yaml"
$WebRoot = Join-Path $RepositoryRoot "apps/web"
$TestExitCode = 1
$FrontendProcess = $null
$FrontendBackupRoot = $null
$GeneratedFrontendFiles = @("next-env.d.ts", "tsconfig.json", "tsconfig.tsbuildinfo")
$E2eNextOutput = Join-Path $WebRoot ".next-e2e"
$FrontendStdout = Join-Path ([System.IO.Path]::GetTempPath()) "api-monitoring-e2e-frontend-$PID.log"
$FrontendStderr = Join-Path ([System.IO.Path]::GetTempPath()) "api-monitoring-e2e-frontend-$PID.error.log"
$PreviousInternalApiBaseUrl = $env:INTERNAL_API_BASE_URL
$PreviousPublicApiBaseUrl = $env:NEXT_PUBLIC_API_BASE_URL
$PreviousSessionCookieName = $env:SESSION_COOKIE_NAME
$PreviousNextDistDir = $env:NEXT_DIST_DIR

try {
    $FrontendBackupRoot = Join-Path ([System.IO.Path]::GetTempPath()) "api-monitoring-e2e-config-$([guid]::NewGuid())"
    New-Item -ItemType Directory -Path $FrontendBackupRoot | Out-Null
    foreach ($GeneratedFile in $GeneratedFrontendFiles) {
        Copy-Item -LiteralPath (Join-Path $WebRoot $GeneratedFile) -Destination $FrontendBackupRoot
    }
    if (Test-Path -LiteralPath $E2eNextOutput) {
        Remove-Item -LiteralPath $E2eNextOutput -Recurse -Force
    }

    & docker compose --project-name $ProjectName --file $ComposeFile up `
        --build `
        --detach `
        --wait
    if ($LASTEXITCODE -ne 0) {
        $TestExitCode = $LASTEXITCODE
    }
    else {
        $env:INTERNAL_API_BASE_URL = "http://127.0.0.1:8800"
        $env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8800"
        $env:SESSION_COOKIE_NAME = "amp_e2e_session"
        $env:NEXT_DIST_DIR = ".next-e2e"
        $FrontendProcess = Start-Process `
            -FilePath "npm.cmd" `
            -ArgumentList @("run", "dev", "--", "-H", "127.0.0.1", "-p", "3300") `
            -WorkingDirectory $WebRoot `
            -WindowStyle Hidden `
            -RedirectStandardOutput $FrontendStdout `
            -RedirectStandardError $FrontendStderr `
            -PassThru

        $FrontendReady = $false
        for ($Attempt = 1; $Attempt -le 60; $Attempt++) {
            if ($FrontendProcess.HasExited) { break }
            try {
                $Response = Invoke-WebRequest -Uri "http://127.0.0.1:3300/health" -TimeoutSec 2 -UseBasicParsing
                if ($Response.StatusCode -eq 200) {
                    $FrontendReady = $true
                    break
                }
            }
            catch {
                Start-Sleep -Seconds 1
            }
        }
        if (-not $FrontendReady) {
            throw "E2E frontend did not become healthy. Logs: $FrontendStdout and $FrontendStderr"
        }

        Push-Location $WebRoot
        try {
            $Arguments = @("run", "test:e2e", "--")
            if ($Grep) { $Arguments += @("--grep", $Grep) }
            if ($Headed) { $Arguments += "--headed" }
            & npm @Arguments
            $TestExitCode = $LASTEXITCODE
        }
        finally {
            Pop-Location
        }
    }
}
finally {
    if ($null -ne $FrontendProcess -and -not $FrontendProcess.HasExited) {
        & taskkill.exe /PID $FrontendProcess.Id /T /F 2>$null | Out-Null
    }
    if (Test-Path -LiteralPath $E2eNextOutput) {
        Remove-Item -LiteralPath $E2eNextOutput -Recurse -Force
    }
    if ($null -ne $FrontendBackupRoot -and (Test-Path -LiteralPath $FrontendBackupRoot)) {
        foreach ($GeneratedFile in $GeneratedFrontendFiles) {
            Copy-Item -LiteralPath (Join-Path $FrontendBackupRoot $GeneratedFile) -Destination $WebRoot -Force
        }
        Remove-Item -LiteralPath $FrontendBackupRoot -Recurse -Force
    }
    if ($null -eq $PreviousInternalApiBaseUrl) { Remove-Item Env:INTERNAL_API_BASE_URL -ErrorAction SilentlyContinue }
    else { $env:INTERNAL_API_BASE_URL = $PreviousInternalApiBaseUrl }
    if ($null -eq $PreviousPublicApiBaseUrl) { Remove-Item Env:NEXT_PUBLIC_API_BASE_URL -ErrorAction SilentlyContinue }
    else { $env:NEXT_PUBLIC_API_BASE_URL = $PreviousPublicApiBaseUrl }
    if ($null -eq $PreviousSessionCookieName) { Remove-Item Env:SESSION_COOKIE_NAME -ErrorAction SilentlyContinue }
    else { $env:SESSION_COOKIE_NAME = $PreviousSessionCookieName }
    if ($null -eq $PreviousNextDistDir) { Remove-Item Env:NEXT_DIST_DIR -ErrorAction SilentlyContinue }
    else { $env:NEXT_DIST_DIR = $PreviousNextDistDir }
    & docker compose --project-name $ProjectName --file $ComposeFile down `
        --volumes `
        --remove-orphans
    if ($LASTEXITCODE -ne 0 -and $TestExitCode -eq 0) {
        $TestExitCode = $LASTEXITCODE
    }
    if ($TestExitCode -eq 0) {
        Remove-Item $FrontendStdout, $FrontendStderr -ErrorAction SilentlyContinue
    }
}

exit $TestExitCode
