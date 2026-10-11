#Requires -Version 5.1
<#
.SYNOPSIS
    Muestra qué cambió en cada fuente de skills y, si lo apruebas, mueve el commit fijado.

.DESCRIPTION
    Para cada fuente de skills.lock.json trae el último commit (o el último tag, en el
    plugin de EL4CTEO), muestra "git log --oneline <fijado>..<nuevo>" y el diffstat, y
    pregunta antes de tocar skills.lock.json. Si algo cambió, vuelve a ejecutar setup.ps1.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\update-skills.ps1
#>
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot

Push-Location $Repo
try {
    python (Join-Path $PSScriptRoot 'skills_sync.py') update
    $code = $LASTEXITCODE
    if ($code -eq 3) {
        Write-Host ''
        Write-Host 'Reinstalando con los commits nuevos...' -ForegroundColor Cyan
        & (Join-Path $PSScriptRoot 'setup.ps1') -GamesHome no
        $code = $LASTEXITCODE
        Write-Host ''
        Write-Host 'Revisa los cambios y haz commit:  git diff skills.lock.json .claude/settings.json'
    }
    exit $code
} finally {
    Pop-Location
}
