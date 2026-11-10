# AiDocMaker - Packaging Script for Cloud Deployment (Windows PowerShell)

param(
    [string]$ServerIP = "YOUR_SERVER_IP",
    [string]$ServerUser = "ubuntu",
    [string]$OutputFile = "aidocmaker-deploy.tar.gz"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================================"
Write-Host "   Packaging AiDocMaker for Cloud Deployment"
Write-Host "========================================================"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
Set-Location $ProjectDir

Write-Host "Target Directory: $ProjectDir"

if (Test-Path $OutputFile) {
    Remove-Item $OutputFile -Force
}

$tarArgs = @(
    "--exclude=node_modules",
    "--exclude=.venv",
    "--exclude=venv",
    "--exclude=apps/api/.venv",
    "--exclude=apps/api/venv",
    "--exclude=apps/web/node_modules",
    "--exclude=apps/web/dist",
    "--exclude=.git",
    "--exclude=.pytest_cache",
    "--exclude=__pycache__",
    "-czvf",
    $OutputFile,
    "docker-compose.yml",
    "deploy.sh",
    "aiqms.db",
    "data",
    "apps",
    ".env"
)

Write-Host "Creating archive: $OutputFile..."
& tar.exe @tarArgs

if (Test-Path $OutputFile) {
    $sizeMb = [Math]::Round((Get-Item $OutputFile).Length / 1MB, 2)
    Write-Host "Package created successfully: $OutputFile ($sizeMb MB)"
    Write-Host ""
    Write-Host "========================================================"
    Write-Host "   Next Steps to Deploy to Linux Server:"
    Write-Host "========================================================"
    Write-Host "1. Upload to your cloud server:"
    Write-Host "   scp $OutputFile ${ServerUser}@${ServerIP}:/home/${ServerUser}/"
    Write-Host ""
    Write-Host "2. SSH into your server and run:"
    Write-Host "   ssh ${ServerUser}@${ServerIP}"
    Write-Host "   tar -xzvf $OutputFile"
    Write-Host "   chmod +x deploy.sh"
    Write-Host "   ./deploy.sh"
    Write-Host "========================================================"
} else {
    Write-Error "Failed to generate $OutputFile"
}
