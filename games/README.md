# games/

Cada juego vive en `games/<NombreJuego>/` como un **proyecto Rojo independiente**. Esta
carpeta está ignorada por el git del estudio (salvo este README y `.gitkeep`): cada juego
tiene su propio repositorio.

`ROBLOX_GAMES_HOME` debe apuntar aquí. El setup ofrece configurarla:

```powershell
setx ROBLOX_GAMES_HOME "C:\ruta\a\roblox-ai-studio\games"     # Windows (terminal nueva después)
```
```bash
export ROBLOX_GAMES_HOME="$HOME/ruta/a/roblox-ai-studio/games" # macOS/Linux, en ~/.zshrc o ~/.bashrc
```

## Crear un juego

**Opción A: con Claude (recomendada).** En Claude Code, desde la raíz del repo:

> complete the research and plan stage for an obby game

`create-roblox-game` hace la sección 1 (investigación y plan) y crea la carpeta del juego.
El código llega en la sección 2.

**Opción B: a mano, solo el proyecto de código.**

```bash
python ~/.claude/skills/roblox-code/scripts/new_project.py "Coin Dash" --dir "$ROBLOX_GAMES_HOME/CoinDash"
```

En PowerShell: `--dir "$env:ROBLOX_GAMES_HOME\CoinDash"`.

## Preparar y comprobar

Dentro de la carpeta del juego:

```bash
rokit install      # lee el aftman.toml del juego (las skills dicen "aftman install"; es lo mismo)
wally install      # Knit, Promise, Signal, Trove -> Packages/
python ~/.claude/skills/roblox-code/scripts/check.py   # 4 revisiones: deben salir en verde
rojo serve         # luego, en Studio: plugin de Rojo -> Connect (una sola conexión)
```

La primera vez, instala el plugin de Rojo en Studio con `rojo plugin install`. Hazlo
dentro del juego, después de `rokit install`, para que use la versión de Rojo fijada.

Un proyecto recién creado ya pasa las 4 revisiones. Si no pasan, arréglalo antes de
escribir código de juego.

## Darle a cada juego su propio git

```bash
cd games/CoinDash
git init -b main
git add -A
git commit -m "chore: scaffold Coin Dash"
gh repo create CoinDash --private --source . --push   # opcional, con GitHub CLI
```

El generador escribe un `.gitignore` con `Packages/`, `ServerPackages/`, `DevPackages/`,
`*.rbxlx.lock` y `sourcemap.json`. Añádele `*.rbxl` y `*.rbxlx`: los archivos de lugar
se generan con `rojo build` y no se versionan. Versiona en cambio:

- `assets/audio/audio.lock.json`, si usas `own-audio`;
- `CREDITS.md`, con las atribuciones que pidan los packs de VFX y demás recursos (ver `docs/licenses.md`).
