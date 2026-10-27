param([switch]$Pull, [string]$Model = 'qwen3.5:9b')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = Join-Path (Get-Location) '.partlens\local-llm\models'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$localExecutable = Join-Path (Get-Location) '.partlens\local-llm\runtime\ollama.exe'
if (-not (Test-Path -LiteralPath $localExecutable)) {
    throw 'Install the official standalone Ollama runtime in .partlens/local-llm/runtime first. See DEVELOPMENT.md.'
}
try {
    $null = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
    Write-Output 'An Ollama runtime is already listening on loopback.'
} catch {
    $localStamp = Get-Date -Format 'yyyyMMddTHHmmss'
    $localLogs = Join-Path (Get-Location) '.partlens\local-llm'
    $localProcess = Start-Process -FilePath $localExecutable -ArgumentList 'serve' -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $localLogs "server-$localStamp.stdout.log") `
        -RedirectStandardError (Join-Path $localLogs "server-$localStamp.stderr.log") -PassThru
    Write-Output "Started loopback-only Ollama, PID $($localProcess.Id), cloud disabled."
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $null = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
            break
        } catch { if ($attempt -eq 29) { throw } }
    }
}
if ($Pull) {
    & $localExecutable pull $Model
    if ($LASTEXITCODE -ne 0) { throw 'Model download failed; no cloud fallback attempted.' }
}
& $localExecutable list
