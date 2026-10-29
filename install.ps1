# RoNavi Studio installer for Windows (PowerShell 5.1+). Run it again to update.
#
#   irm https://raw.githubusercontent.com/Andres-devp/RoNavi/main/install.ps1 | iex
#
# 1. Checks git and Python 3.11+ (offers winget when one is missing).
# 2. Clones the studio into $env:RONAVI_HOME (default: $HOME\RoNavi) at the newest release
#    tag (vX.Y.Z), or runs "ronavi update" when it is already there.
# 3. Puts "ronavi" on your user PATH and opens RoNavi Studio (the setup wizard does the rest).
#
# Optional: $env:RONAVI_HOME (folder), $env:RONAVI_REPO (git URL), $env:RONAVI_NO_START = 1,
# $env:RONAVI_NO_PATH = 1 (portable install: PATH untouched, nothing is started).
# The file is ASCII on purpose: "irm | iex" and Windows PowerShell 5.1 disagree on encodings.

& {
    $ErrorActionPreference = 'Stop'
    $repo = if ($env:RONAVI_REPO) { $env:RONAVI_REPO } else { 'https://github.com/Andres-devp/RoNavi.git' }
    $target = if ($env:RONAVI_HOME) { $env:RONAVI_HOME } else { Join-Path $HOME 'RoNavi' }

    function Say([string]$msg) {
        Write-Host 'RoNavi Studio ' -ForegroundColor DarkYellow -NoNewline
        Write-Host $msg
    }

    function Update-SessionPath {
        $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                    [Environment]::GetEnvironmentVariable('Path', 'User')
    }

    function Ask([string]$question) {
        $answer = Read-Host "$question [S/n]"
        return ($answer -eq '' -or $answer -match '^[sSyY]')
    }

    function Install-WithWinget([string]$id, [string]$label) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            Say "Falta $label y no hay winget. Instalalo a mano y vuelve a ejecutar este comando."
            return $false
        }
        if (-not (Ask "Falta $label. Instalarlo ahora con winget?")) { return $false }
        winget install --id $id -e --accept-source-agreements
        Update-SessionPath
        return $true
    }

    # A real Python 3.11+, never the Microsoft Store stub.
    function Find-Python {
        foreach ($candidate in @(@('py', '-3'), @('python'))) {
            if (-not (Get-Command $candidate[0] -ErrorAction SilentlyContinue)) { continue }
            $exe = $candidate[0]
            $rest = @($candidate | Select-Object -Skip 1)
            try {
                # No quotes inside the code: Windows PowerShell 5.1 drops them when calling native programs.
                $out = & $exe @rest -c 'import sys; print(sys.executable) if sys.version_info >= (3, 11) else None' 2>$null
            } catch { continue }
            if ($LASTEXITCODE -eq 0 -and $out -and (Test-Path $out)) { return [string]$out }
        }
        return $null
    }

    function Test-Studio([string]$dir) {
        return (Test-Path (Join-Path $dir 'skills.lock.json')) -and
               (Test-Path (Join-Path $dir 'scripts\doctor.py')) -and
               (Test-Path (Join-Path $dir 'ronavi\__init__.py'))
    }

    Update-SessionPath

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        if (-not (Install-WithWinget 'Git.Git' 'git') -or -not (Get-Command git -ErrorAction SilentlyContinue)) {
            Say 'Sin git no se puede instalar. Abre una terminal nueva cuando lo tengas y repite el comando.'
            return
        }
    }
    $python = Find-Python
    if (-not $python) {
        [void](Install-WithWinget 'Python.Python.3.12' 'Python 3.11 o superior')
        $python = Find-Python
        if (-not $python) {
            Say 'Sin Python 3.11+ no se puede seguir. Abre una terminal nueva cuando lo tengas y repite el comando.'
            return
        }
    }
    $boot = Join-Path $target 'ronavi\bootstrap.py'

    if (Test-Studio $target) {
        Say "Ya estaba instalado en $target. Buscando una version nueva..."
        & $python $boot update
        if ($LASTEXITCODE -ne 0) { Say 'No se pudo actualizar; se mantiene la version instalada.' }
    } elseif ((Test-Path $target) -and (Get-ChildItem -Force $target | Select-Object -First 1)) {
        Say "$target ya existe y no es RoNavi Studio. Elige otra carpeta con: `$env:RONAVI_HOME = 'C:\otra\carpeta'"
        return
    } else {
        Say "Descargando en $target"
        git clone --quiet $repo $target
        if ($LASTEXITCODE -ne 0) { Say 'git clone fallo.'; return }
        $tag = git -C $target tag --list 'v*' --sort=-v:refname | Select-Object -First 1
        if ($tag) {
            Say "Version $tag"
            git -C $target -c advice.detachedHead=false checkout --quiet $tag
        } else {
            Say 'Aun no hay versiones publicadas: se usa la rama main.'
        }
    }

    if ($env:RONAVI_NO_PATH) {
        Say "PATH sin tocar (RONAVI_NO_PATH). Arranca con: $target\ronavi.cmd"
        return
    }
    & $python $boot path add
    Say 'Listo. En cualquier terminal nueva escribe: ronavi'
    if (-not $env:RONAVI_NO_START) {
        & $python $boot
    }
}
