# RoNavi Studio (roblox-ai-studio)

Estudio para crear juegos de Roblox con Claude Code. **Respóndeme siempre en español.**
La interfaz es **RoNavi Studio** (`ronavi.cmd` / `ronavi.sh`, código en `ronavi/`): instala, crea juegos
y abre Claude Code dentro de cada uno. Guía: `docs/ronavi.md`.
Documentación para humanos en español; código, nombres de archivo e identificadores en inglés.

## Mapa del repo

- `games/<Juego>/`: cada juego es un proyecto Rojo independiente, con su propio git, su `CLAUDE.md`, su `.claude/` y un guardián (`.claude/hooks/ronavi_guard.py`); fuera del git de este repo. `ROBLOX_GAMES_HOME` apunta a `games/`.
- `work/ideas/<fecha>/`: ideas de RoNavi (investigación antes de tener juego; sin git, con su propio guardián). Al convertirse en juego, su investigación pasa a `docs/research/` del juego.
- `ronavi/`: RoNavi Studio (Python + Textual). `core/` sin interfaz (rutas, guard, proyectos, entorno, integraciones), `ui/` la TUI, `assets/ronavi_guard.py` el hook de cada juego. `tests/`: sus pruebas (`unittest`).
- `.claude/skills/`: skills de proyecto.
  - Propias (versionadas): `studio-doctor`, `quota-guard`, `own-audio`.
  - De terceros (las copia el setup): `figma-to-roblox-ui`, `roblox-game-design`, `roblox-player-psychology`.
- `~/.claude/skills` y `~/.claude/agents`: skills y agentes de SyphoDev, a nivel usuario.
- Plugins: `roblox-skills@roblox-skills` (EL4CTEO, conocimiento) y `figma@claude-plugins-official`.
- `docs/`: `ronavi.md`, `pipeline.md`, `mcp.md`, `quotas.md` (única fuente de cifras), `licenses.md`, `troubleshooting.md`, `decisions.md`.
- `scripts/`: `setup.*`, `update-skills.*`, `doctor.py`, `skills_sync.py`. `skills.lock.json` fija los commits de terceros.

## Enrutamiento de skills

| Tarea | Skill |
|---|---|
| Juego completo o por etapas ("complete the research and plan stage…", "continue with…", "approved") | `create-roblox-game` |
| Escribir o revisar código, crear el proyecto, revisiones | `roblox-code` (+ conocimiento: `roblox-skills:roblox-luau`, `roblox-skills:roblox-networking`, `roblox-skills:roblox-security`, `roblox-skills:roblox-data-stores`) |
| UI desde una spec JSON | `roblox-ui` |
| UI desde un diseño de Figma | `figma-to-roblox-ui` + MCP `figma` |
| Mapas y niveles | `roblox-map` |
| Modelos 3D | `roblox-3d-model` (+ `roblox-texture-gen` para texturas) |
| Animación | `roblox-animation` |
| VFX | `roblox-vfx` |
| Sonidos de la Creator Store | `roblox-sfx` |
| Mis propios sonidos y música (WAV de mi DAW) | `own-audio` |
| Diseño, bucles de juego, retención | `roblox-game-design`, `roblox-player-psychology` |
| Manejar Studio por MCP | `roblox-skills:roblox-studio-mcp` |
| **Antes** de usar cualquier servicio con cupo (Cloudflare, Kaggle, Figma, Open Cloud, procedurales de Studio, ZeroGPU) | `quota-guard` |
| Algo de MCP, Rojo o las skills falla, o máquina nueva | `studio-doctor` |
| Varias fases de assets en paralelo | `roblox-build-orchestrator` |

## Reglas de trabajo

Las 5 reglas de `roblox-code`:

1. **El disco es la única verdad.** El código se edita en disco y llega a Studio por Rojo. Nunca edites scripts dentro de Studio ni los sobrescribas por MCP: el MCP es para geometría, inspección y capturas.
2. **La lógica pura va en `src/shared/Core/`.** Si una función puede escribirse sin tocar una Instance, va ahí y lleva su spec.
3. **La red pasa por un solo `Net.luau`**, con RemoteEvents simples declarados en un único lugar.
4. **Lo cosmético nunca rompe la jugabilidad.** Los efectos son asíncronos, aislados con `pcall` y fallan sin consecuencias.
5. **Todo valor ajustable va en `src/shared/Config/`.** Equilibrar el juego es editar datos, no código.

Además:

- **Si la sesión empezó dentro de `games/<Juego>/`, ese juego es tu único ámbito de escritura.** No edites la plantilla ni otros juegos; si el guardián de RoNavi bloquea algo, no lo esquives: pídeselo al usuario.
- **Script Sync de Studio apagado.** Una sola conexión de Rojo.
- **Un solo servidor MCP de Studio a la vez.** `Roblox_Studio` por defecto; `robloxstudio-runtime` solo para depurar en vivo, con el oficial apagado (ver `docs/mcp.md`).
- Llama a `get_studio_state` en **cada cambio de etapa**; no supongas si Studio está en Edit o en Play.
- `execute_luau` corre en el DataModel del plugin: **nunca asumas que ve el juego en ejecución**. Para leer estado vivo, imprime desde el juego y léelo con `get_console_output`.
- **Los subagentes nunca escriben en Studio.** Trabajan en disco y devuelven resultados; el hilo principal ensambla. Sus agentes ya tienen bloqueados `mcp__Roblox_Studio` y `mcp__robloxstudio-runtime`.
- **Knit está archivado.** En juegos nuevos usa el scaffold de `new_project.py` tal cual y no lo mezcles con otro framework.
- Todo lo que escribe en Studio o gasta cupo (`execute_luau`, `multi_edit`, `start_stop_play`, `insert_asset`, `generate_*`, `upload_image`) pide permiso: explica qué vas a hacer antes.
- En `create-roblox-game`: una sección por sesión, con `HANDOFF.md` al cerrar. No empieces la siguiente sin "approved".

## Comandos

Dentro de `games/<Juego>/`:

```bash
rokit install          # instala la toolchain fijada; equivale a "aftman install" de las skills
wally install          # paquetes (Knit, Promise, Signal, Trove)
python ~/.claude/skills/roblox-code/scripts/check.py   # las 4 revisiones: rojo build, lune, selene, stylua
rojo serve             # y conectar el plugin de Rojo en Studio (una vez)
```

Desde la raíz del repo:

```bash
.\ronavi                                                  # RoNavi Studio (Windows); sh ronavi.sh en macOS/Linux
python scripts/validate.py                                # lo mismo que la CI, incluidas las pruebas de ronavi/
python scripts/doctor.py                                  # estado de la máquina
python .claude/skills/quota-guard/scripts/quota.py status # cupos
```

## Secretos

Las claves viven **solo** en variables de entorno: `ROBLOX_API_KEY`, `ROBLOX_USER_ID` / `ROBLOX_GROUP_ID`,
`CF_ACCOUNT_ID`, `CF_API_TOKEN`, `KAGGLE_API_TOKEN` (o `~/.kaggle/kaggle.json`), `HF_TOKEN`.

- En archivos, `LOCAL.md` o documentación se escribe solo el **nombre** de la variable.
- Nunca pidas un valor en el chat: explica cómo ponerlo con `setx` (Windows) o `export` (macOS/Linux) en la terminal del usuario.
- No leas `.env*` ni `kaggle.json`.

## Definición de terminado de cada cambio

1. `check.py` en verde: las 4 revisiones pasan.
2. Playtest descrito: qué se probó en Studio, qué se vio en Output (incluida la marca de build) y qué falta probar.
3. Commit pequeño con Conventional Commits en el repo del juego, o en este repo si el cambio es de la plantilla.
