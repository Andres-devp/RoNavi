# Cambios de RoNavi Studio

Cada versión es un tag `vX.Y.Z` con su GitHub Release (las notas salen de esta página).
El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones,
[SemVer](https://semver.org/lang/es/). Cómo publicar una: `docs/ronavi.md` → *Versiones*.

## [0.2.0] - 2026-10-29

### Añadido

- **Explorar idea**: investiga un juego sin ponerle nombre, género ni descripción. Claude trabaja en
  `work/ideas/<fecha>/`, sin git, con su propio guardián, y escribe tres conceptos en `IDEA.md`.
  Desde *Nuevo juego → Ideas guardadas* la idea se convierte en juego y su investigación se copia a
  `docs/research/`. En la CLI: `ronavi idea`, `ronavi ideas` y `ronavi new … --from-idea <id>`.
- **Instalador de una línea**: `install.ps1` (Windows) e `install.sh` (macOS/Linux) clonan el estudio
  en la última versión, ponen `ronavi` en el PATH y lo abren. Volver a ejecutarlos actualiza.
- **Actualizar**: `ronavi update` y *Configuración → Actualizar RoNavi*. Una instalación pasa al tag
  más nuevo; un clon de desarrollo hace `git pull --ff-only`. Al arrancar, RoNavi avisa (una vez al día)
  si hay una versión nueva.
- **Actualizar todo**: `ronavi update --all` y *Configuración → Actualizar todo*: RoNavi, skills,
  plugins, guardianes y toolchain de cada juego, sin parar si un paso falla y con un resumen ✔/✘.
- **Luau LSP para Claude**: el plugin local `ronavi-luau` da a Claude los diagnósticos de luau-lsp, con
  los tipos de Roblox, tras cada edición de un `.luau` (D20).
- **Revisión tras cada edición**: un hook `PostToolUse` en cada juego formatea con StyLua y pasa Selene al
  `.luau` que Claude acaba de tocar.
- Los juegos nuevos salen con Rojo 7.7.1, Selene 0.32.0, StyLua 2.6.0 y luau-lsp 1.70.1. Lune se queda en
  0.8.9 porque las versiones nuevas rompen las specs del scaffold (D21).
- Skill **`own-images`**: sube tus imágenes (iconos, decals, UI) con Asphalt, sin resubir lo que no cambió, y
  genera un módulo Luau con los IDs (D22).
- Skill **`cloud-test`**: corre las specs del juego en un servidor real de Roblox con Open Cloud Luau Execution,
  en un place de pruebas. Las specs que necesitan el motor van en `tests/engine/` (D23).
- `ronavi path [add]` y un paso del asistente para escribir `ronavi` en cualquier terminal.
- `ronavi --version` muestra también el tag o commit de git.
- Workflow `release` que publica la GitHub Release al subir un tag `vX.Y.Z`.

### Cambiado

- `robloxstudio-runtime` pasa a 3.4.2. Sus herramientas que editan scripts quedan bloqueadas y las que
  tocan tu cuenta siempre preguntan (D19). Al sincronizar, cada juego recibe el pin y las reglas nuevas.
- `docs/mcp.md` al día: 32 herramientas del MCP oficial, Quick Connect, `studio_id` obligatorio y por qué
  no instalar el plugin oficial de Roblox junto a `Roblox_Studio`.

## [0.1.0] - 2026-10-11

### Añadido

- Primera versión de RoNavi Studio: interfaz de terminal, juegos aislados con su propio git y guardián,
  asistente de instalación, skills, herramientas e integraciones.
