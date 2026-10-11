#Requires -Version 5.1
<#
.SYNOPSIS
    Prepara roblox-ai-studio en Windows. Se puede ejecutar varias veces.

.DESCRIPTION
    1. Comprueba git, python (3.11+) y claude.
    2. Clona o actualiza las fuentes de skills.lock.json en vendor/ y hace checkout del commit fijado.
    3. SyphoDev: ejecuta su propio install.ps1 (respeta LOCAL.md y hace copia de respaldo)
       y parcha sus agentes para que no puedan usar el MCP de Studio.
    4. Copia las skills de proyecto a .claude/skills/.
    5. Añade los marketplaces e instala los plugins (roblox-skills, figma).
    6. Instala las dependencias de Python (pip --user).
    7. Ofrece configurar ROBLOX_GAMES_HOME = <repo>\games (pregunta antes).
    8. Ejecuta doctor.py y muestra los pasos manuales.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -GamesHome no
#>
param(
    # Vuelve a ejecutar el instalador de SyphoDev aunque ya esté al día.
    [switch]$Force,
    # ask = preguntar; yes / no = responder sin preguntar.
    [ValidateSet('ask', 'yes', 'no')][string]$GamesHome = 'ask'
)

$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
$Sync = Join-Path $PSScriptRoot 'skills_sync.py'

function Write-Step([int]$n, [string]$text) {
    Write-Host ''
    Write-Host "[$n/8] $text" -ForegroundColor Cyan
}

function Stop-Setup([string]$msg) {
    Write-Host "ERROR: $msg" -ForegroundColor Red
    exit 1
}

function Invoke-Checked([string]$what, [scriptblock]$block) {
    & $block
    if ($LASTEXITCODE -ne 0) { Stop-Setup "$what falló (código $LASTEXITCODE)." }
}

Push-Location $Repo
try {
    Write-Step 1 'Comprobando git, python y claude'
    $missing = @()
    foreach ($tool in 'git', 'python', 'claude') {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { $missing += $tool }
    }
    if ($missing.Count -gt 0) {
        Write-Host "Faltan: $($missing -join ', ')" -ForegroundColor Red
        Write-Host '  git    -> winget install Git.Git'
        Write-Host '  python -> winget install Python.Python.3.12'
        Write-Host '  claude -> https://code.claude.com/docs/en/setup'
        Stop-Setup 'Instala lo que falta, abre una terminal nueva y vuelve a ejecutar el setup.'
    }
    & python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'
    if ($LASTEXITCODE -ne 0) {
        Stop-Setup 'Se necesita Python 3.11 o superior (winget install Python.Python.3.12).'
    }
    Write-Host '  ok git, python, claude'

    Write-Step 2 'Fuentes fijadas en vendor/'
    Invoke-Checked 'skills_sync vendor' { python $Sync vendor }

    Write-Step 3 'Skills y agentes de SyphoDev (nivel usuario)'
    if ($Force) {
        Invoke-Checked 'skills_sync user' { python $Sync user --force }
    } else {
        Invoke-Checked 'skills_sync user' { python $Sync user }
    }

    Write-Step 4 'Skills de proyecto'
    Invoke-Checked 'skills_sync project' { python $Sync project }

    Write-Step 5 'Plugins de Claude Code'
    Invoke-Checked 'skills_sync plugins' { python $Sync plugins }
    Invoke-Checked 'skills_sync local-settings' { python $Sync local-settings }

    Write-Step 6 'Dependencias de Python'
    Invoke-Checked 'pip install' {
        python -m pip install --user --disable-pip-version-check --quiet -r (Join-Path $Repo 'requirements.txt')
    }
    Write-Host '  ok requirements.txt'

    Write-Step 7 'ROBLOX_GAMES_HOME'
    $target = Join-Path $Repo 'games'
    $current = [Environment]::GetEnvironmentVariable('ROBLOX_GAMES_HOME', 'User')
    if ($current -eq $target) {
        Write-Host "  ok ya apunta a $target"
    } else {
        $answer = $GamesHome
        if ($answer -eq 'ask') {
            if ($current) { Write-Host "  Ahora apunta a: $current" }
            try {
                $reply = Read-Host "  ¿Configurar ROBLOX_GAMES_HOME = $target para tu usuario? (s/N)"
            } catch {
                $reply = ''
            }
            $answer = if ($reply -match '^(s|si|sí|y|yes)$') { 'yes' } else { 'no' }
        }
        if ($answer -eq 'yes') {
            # Same effect as setx, without setx's 1024-character truncation.
            [Environment]::SetEnvironmentVariable('ROBLOX_GAMES_HOME', $target, 'User')
            $env:ROBLOX_GAMES_HOME = $target
            Write-Host "  ok ROBLOX_GAMES_HOME = $target (las terminales nuevas la verán)"
        } else {
            Write-Host '  omitido. Para hacerlo luego:'
            Write-Host "    setx ROBLOX_GAMES_HOME `"$target`""
        }
    }

    Write-Step 8 'Diagnóstico'
    python (Join-Path $PSScriptRoot 'doctor.py')
    $doctorExit = $LASTEXITCODE

    Write-Host ''
    Write-Host 'Pasos manuales que quedan:' -ForegroundColor Yellow
    Write-Host '  1. Roblox Studio: Assistant > ... > Manage MCP Servers > "Enable Studio as MCP server" (indicador verde).'
    Write-Host '     Script Sync APAGADO. Plugin de Rojo: dentro de un juego, "rokit install" y luego "rojo plugin install".'
    Write-Host '  2. Abre "claude" en esta carpeta y acepta la confianza del espacio de trabajo.'
    Write-Host '     /mcp para autenticar figma; /roblox-skills-setup para escribir los LOCAL.md.'
    Write-Host '  3. Variables de entorno con setx en TU terminal (nunca en el chat): ver README, sección 3.'
    Write-Host '  4. Comprueba de nuevo con: python scripts/doctor.py'
    if ($doctorExit -ne 0) {
        Write-Host ''
        Write-Host 'doctor.py encontró algo obligatorio sin resolver (filas con X roja).' -ForegroundColor Yellow
    }
    exit $doctorExit
} finally {
    Pop-Location
}
