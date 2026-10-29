# MCP en este estudio

Hay cuatro servidores MCP posibles. Solo uno está encendido por defecto.

| Servidor | Qué es | Estado por defecto | Dónde se declara |
|---|---|---|---|
| `Roblox_Studio` | MCP oficial, integrado en Roblox Studio | **Encendido** | `.mcp.json` + `enabledMcpjsonServers` en `.claude/settings.json` |
| `figma` | MCP remoto de Figma, viene con el plugin `figma@claude-plugins-official` | Encendido (pide autenticación con `/mcp`) | Plugin |
| `blender-ahujasid` | [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp) (paquete `mcp-for-blender`) | Apagado | `.mcp.json` + `.claude/settings.local.json` |
| `robloxstudio-runtime` | [`@chrrxs/robloxstudio-mcp`](https://www.npmjs.com/package/@chrrxs/robloxstudio-mcp) 3.4.2, para depurar el juego en ejecución | Apagado | `.mcp.json` + `.claude/settings.local.json` |

## El MCP oficial de Studio

Fuentes: [Connect to the Roblox Studio MCP server](https://create.roblox.com/docs/studio/mcp) y la lista de
herramientas que expuso Studio a Claude Code (verificado el 2026-10-29).

**Encenderlo en Studio:** Assistant → **…** → **Manage MCP Servers** → **Enable Studio as MCP server**.
El indicador verde muestra cuántos clientes están conectados. Desde agosto de 2026, *Assistant Settings*
también muestra qué clientes están conectados.

**Quick Connect:** en Assistant Settings → MCP Servers, el desplegable *Quick connect* registra Claude Code
(y Codex, Cursor, Gemini CLI, VS Code…) sin editar archivos. En este estudio no hace falta: `.mcp.json` ya lo trae
con el nombre `Roblox_Studio`, y Quick Connect podría registrar **otro** servidor contra el mismo Studio (regla 1).

**Plugin oficial `Roblox/roblox-studio-agent-plugin`** (7 de octubre de 2026, MIT): solo trae configuración y la
skill `roblox-get-started`. Registra su propio servidor (`plugin:roblox-studio:windows` / `macos`), así que
**no lo instales** junto a `Roblox_Studio`: serían dos clientes contra el mismo Studio con nombres distintos.

**Configuración del cliente:**

- **Windows:** `.mcp.json` ya lo trae, con el comando que da la documentación:
  ```json
  "Roblox_Studio": { "command": "cmd.exe", "args": ["/c", "%LOCALAPPDATA%\\Roblox\\mcp.bat"] }
  ```
  `cmd.exe` expande `%LOCALAPPDATA%` por sí mismo.
- **macOS:** `.mcp.json` no admite configuración por sistema operativo. `scripts/setup.sh` registra el mismo nombre en **scope local**, que tiene prioridad sobre el del proyecto:
  ```bash
  claude mcp add --scope local Roblox_Studio -- /Applications/RobloxStudio.app/Contents/MacOS/StudioMCP
  ```
  `claude mcp list` puede avisar de que `Roblox_Studio` está definido en dos scopes; es lo esperado.
- **Linux:** Roblox Studio no existe para Linux. El resto de la plantilla funciona, pero sin MCP de Studio.

**Herramientas:** la documentación lista 24, pero Studio expone hoy **32**. Las seis que faltan en la
documentación llegaron con las novedades de generación de septiembre de 2026 y con las skills de Studio.
Cuéntalas tú con `/mcp` → `Roblox_Studio` si actualizas Studio.

| Grupo | Herramientas | Permiso en este repo |
|---|---|---|
| Scripts | `script_read`, `script_search`, `script_grep` · `multi_edit` | lectura: permitidas · `multi_edit`: pregunta |
| Generación | `generate_mesh`, `generate_material`, `generate_procedural_model`, `generate_texture`, `segment_mesh`, `wait_job_finished`, `search_asset`, `insert_asset`, `upload_image`, `store_image` | `generate_*`, `segment_mesh`, `insert_asset`, `upload_image`, `store_image`: preguntan. Pasa antes por `quota-guard` |
| Avatar | `auto_setup_avatar` | pregunta |
| DataModel | `search_game_tree`, `inspect_instance`, `subagent` | lectura: permitidas |
| Luau | `execute_luau` (pide `datamodel_type`: Edit, Client o Server) | pregunta |
| Playtest | `get_studio_state`, `get_console_output`, `screen_capture` · `start_stop_play` | lectura: permitidas · `start_stop_play`: pregunta |
| Entrada | `character_navigation`, `user_keyboard_input`, `user_mouse_input` | pregunta (por defecto) |
| Documentación y skills | `http_get`, `skill`, `list_skills` · `create_skill`, `edit_skill` | `create_skill`, `edit_skill`: preguntan · el resto pregunta por defecto |
| Sesión | `list_roblox_studios` | permitida |

Desde el **19 de agosto de 2026** todas las llamadas necesitan un `studio_id` y `set_active_studio` ya no
existe: empieza siempre por `list_roblox_studios`.

## Reglas

1. **Un solo servidor MCP de Studio a la vez.** Dos plugins haciendo long-polling contra el mismo Studio se bloquean. Si enciendes `robloxstudio-runtime`, apaga `Roblox_Studio` durante esa sesión.
2. **Revisa el interruptor después de cada actualización de Studio.** Hubo un fallo (junio de 2026) en el que "Enable Studio as MCP server" se apagaba solo; la actualización del 20 de agosto de 2026 lo da por corregido, junto con los errores "method not implemented". Si vuelve a pasar, es una regresión: repórtala en el foro.
3. **Desconexiones conocidas cada 5–15 minutos** (reportadas en julio de 2026). Lo único que funciona es apagar y volver a encender el interruptor en Studio. Es normal: no gastes tiempo investigando.
4. **`execute_luau` no ve el juego en ejecución.** Corre en el DataModel del plugin, aislado del juego. Para leer estado vivo, imprime desde el código del juego y léelo con `get_console_output`, o usa `robloxstudio-runtime`.
5. **Llama a `get_studio_state` en cada cambio de etapa** en vez de suponer si Studio está en Edit o en Play.
6. **Los subagentes nunca escriben en Studio.** El setup añade `mcp__Roblox_Studio` y `mcp__robloxstudio-runtime` a `disallowedTools` de los agentes de SyphoDev.
7. Un "Target is not reachable" justo después de actualizar Studio suele ser una regresión de Roblox: revisa el foro de bugs de Studio.

## Luau LSP para Claude (`ronavi-luau`)

No es un servidor MCP, pero vive al lado: el plugin local `ronavi-luau@ronavi-studio` arranca
[luau-lsp](https://github.com/JohnnyMorganz/luau-lsp) cuando Claude edita un `.luau`, y Claude recibe los
diagnósticos (tipos de Roblox, `require` rotos, variables sin usar) justo después de cada edición, antes de `check.py`.

- RoNavi genera el marketplace en `.ronavi/plugins/` (no versionado), lo declara en el `settings.local.json`
  de cada juego y lo instala con `claude plugin install … --scope local` la primera vez que abres el juego.
- El juego necesita `luau-lsp` en su `aftman.toml` (RoNavi lo añade, ver D21) y `rokit install`.
- Las definiciones de Roblox y la documentación de la API se guardan en `.ronavi/cache/luau-lsp/` y se
  renuevan cada semana (las mismas que usa la extensión de VS Code, nivel `PluginSecurity`).
- Al arrancar genera `sourcemap.json` (una vez, sin `--watch`, para no dejar procesos colgados) y el hook de
  después de editar lo regenera cuando Claude crea un `.luau`, para que se resuelvan los `require`.
- Comprobarlo: pide a Claude que introduzca un error de tipos en un `.luau`; debe aparecer
  `Found N new diagnostic issues`. Si no, `/plugin` → pestaña **Errors**.

Además, cada juego tiene un hook `PostToolUse` (`.claude/hooks/ronavi_luau_check.py`): tras cada edición de un
`.luau`, formatea el archivo con StyLua y le pasa Selene. Los avisos de Selene vuelven a Claude.

## Encender o apagar los servidores opcionales

Una entrada en `disabledMcpjsonServers` **en cualquier archivo de settings** rechaza el servidor y gana sobre `enabledMcpjsonServers`. Por eso los opcionales se apagan en `.claude/settings.local.json`, que no se versiona y que crea el setup. Así cada persona decide sin tocar el archivo compartido.

Para depurar el juego vivo con `robloxstudio-runtime`, deja `.claude/settings.local.json` así y reinicia Claude Code:

```json
{
  "disabledMcpjsonServers": ["Roblox_Studio", "blender-ahujasid"],
  "enabledMcpjsonServers": ["robloxstudio-runtime"]
}
```

Al terminar, vuelve a dejar `"disabledMcpjsonServers": ["blender-ahujasid", "robloxstudio-runtime"]` y borra `enabledMcpjsonServers`.

### `robloxstudio-runtime`: cuándo usarlo

Úsalo solo cuando necesites estado **vivo** del servidor o del cliente durante un playtest. Por ejemplo:

- `eval_server_runtime` y `eval_client_runtime`, que comparten la caché de `require` del juego;
- breakpoints que registran sin pausar;
- logs por cliente;
- partidas de varios clientes;
- perfiles de CPU y memoria, y sesiones del MicroProfiler de hasta 30 s (`capture_micro_profiler`, desde 3.4.2).

Con `--auto-install-plugin` instala su propio plugin en Studio. Usa la versión fijada (3.4.2) y revisa su
[changelog](https://github.com/Chrrxs/robloxstudio-mcp/releases) antes de subirla. Al sincronizar, RoNavi lleva
la versión fijada del estudio al `.mcp.json` de cada juego.

Permisos en `.claude/settings.json`:

- **Bloqueadas** (regla 1: el disco es la única verdad): `set_script_source`, `edit_script_lines`,
  `insert_script_lines`, `delete_script_lines` y `find_and_replace_in_scripts`.
- **Siempre preguntan** (actúan sobre tu cuenta o insertan contenido): `manage_experience`, `manage_monetization`,
  `upload_asset`, `insert_asset`, `generate_model` e `import_rbxm`.
- El resto pregunta por defecto.

Cambios que rompen desde 3.2.0: los IDs con sufijo de servidor apuntan al servidor por defecto (3.2.1);
`search_objects` devuelve 100 resultados como máximo y busca texto literal, no patrones de Lua (3.3.0);
`classFilter: "Script"` ya no incluye LocalScripts ni ModuleScripts (3.4.0).

### `blender-ahujasid`: cuándo usarlo

El pipeline 3D normal usa Blender **sin ventana** (scripts de `roblox-3d-model`) y no necesita MCP. Enciende este servidor solo para trabajo interactivo en una escena abierta de Blender.

- Necesita `uv` y el addon de Blender. `uvx mcp-for-blender setup` instala el addon. Si la instalación automática falla, mira el README del proyecto.
- En Windows va envuelto en `cmd /c` para evitar el error `ENOENT` al lanzar `uvx`. Lleva `--python 3.11` y `UV_PYTHON_PREFERENCE=only-managed`, como recomienda su README.
- El paquete de PyPI se renombró de `blender-mcp` a `mcp-for-blender`. `uvx blender-mcp` sigue funcionando como alias.
- Se llama `blender-ahujasid`, y no `blender`, para no chocar con otro servidor `blender` que ya tengas a nivel usuario.

## Más información

- Investigación de SyphoDev sobre los dos servidores de Studio, con fallos fechados: `~/.claude/skills/create-roblox-game/references/mcp.md`
- Skill de conocimiento: `roblox-skills:roblox-studio-mcp` (plugin de EL4CTEO)
- Diagnóstico guiado: skill `studio-doctor`
