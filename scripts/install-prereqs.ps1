#Requires -Version 5.1
<#
.SYNOPSIS
    Instala con winget los programas que necesita roblox-ai-studio en un PC con Windows.

.DESCRIPTION
    Ejecútalo TÚ en tu terminal: winget te pedirá aceptar la licencia de cada paquete.
    Lo que ya esté instalado se salta. Se puede ejecutar varias veces.

    Obligatorios: Git, VS Code, Python 3.12, Rokit, uv, Blender 4.5 LTS, Roblox Studio, Claude Code.
    Con -Optional: Node LTS, ffmpeg, PowerShell 7, shellcheck, GitHub CLI.
    Además instala las extensiones recomendadas de VS Code.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\install-prereqs.ps1
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\install-prereqs.ps1 -Optional
#>
param(
    # También instala los programas opcionales.
    [switch]$Optional
)

$ErrorActionPreference = 'Continue'

$required = @(
    @{ Id = 'Git.Git';                            Name = 'Git' },
    @{ Id = 'Microsoft.VisualStudioCode';         Name = 'VS Code' },
    @{ Id = 'Python.Python.3.12';                 Name = 'Python 3.12' },
    @{ Id = 'Rojo.Rokit';                         Name = 'Rokit' },
    @{ Id = 'astral-sh.uv';                       Name = 'uv' },
    @{ Id = 'BlenderFoundation.Blender.LTS.4.5';  Name = 'Blender 4.5 LTS' },
    @{ Id = 'Roblox.RobloxStudio';                Name = 'Roblox Studio' }
)
$optionalPkgs = @(
    @{ Id = 'OpenJS.NodeJS.LTS';    Name = 'Node LTS' },
    @{ Id = 'Gyan.FFmpeg';          Name = 'ffmpeg' },
    @{ Id = 'Microsoft.PowerShell'; Name = 'PowerShell 7' },
    @{ Id = 'koalaman.shellcheck';  Name = 'shellcheck' },
    @{ Id = 'GitHub.cli';           Name = 'GitHub CLI' }
)

function Update-SessionPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Install-Package([hashtable]$pkg) {
    winget list --id $pkg.Id -e --accept-source-agreements *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ok    $($pkg.Name) ya está instalado"
        return
    }
    Write-Host "  install $($pkg.Name) ($($pkg.Id))" -ForegroundColor Cyan
    winget install --id $pkg.Id -e
    if ($LASTEXITCODE -ne 0) { Write-Host "  !! falló $($pkg.Name) (código $LASTEXITCODE)" -ForegroundColor Yellow }
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host 'No se encuentra winget. Instala "App Installer" desde Microsoft Store y vuelve a intentarlo.' -ForegroundColor Red
    exit 1
}

Write-Host 'Programas obligatorios' -ForegroundColor Cyan
foreach ($p in $required) { Install-Package $p }

Update-SessionPath
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    # Native installer from the official docs: unlike the winget package, it auto-updates.
    Write-Host '  install Claude Code (instalador oficial)' -ForegroundColor Cyan
    Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression
} else {
    Write-Host '  ok    Claude Code ya está instalado'
}

if ($Optional) {
    Write-Host ''
    Write-Host 'Programas opcionales' -ForegroundColor Cyan
    foreach ($p in $optionalPkgs) { Install-Package $p }
}

Update-SessionPath
if (Get-Command code -ErrorAction SilentlyContinue) {
    Write-Host ''
    Write-Host 'Extensiones de VS Code' -ForegroundColor Cyan
    foreach ($ext in 'evaera.vscode-rojo', 'JohnnyMorganz.luau-lsp', 'Kampfkarren.selene-vscode', 'JohnnyMorganz.stylua') {
        code --install-extension $ext --force | Out-Null
        Write-Host "  ok    $ext"
    }
}

Write-Host ''
Write-Host 'Listo. Siguiente paso, en esta misma terminal:' -ForegroundColor Green
Write-Host '  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1'
