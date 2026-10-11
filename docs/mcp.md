# MCP en este estudio

Hay cuatro servidores MCP posibles. Solo uno está encendido por defecto.

| Servidor | Qué es | Estado por defecto | Dónde se declara |
|---|---|---|---|
| `Roblox_Studio` | MCP oficial, integrado en Roblox Studio | **Encendido** | `.mcp.json` + `enabledMcpjsonServers` en `.claude/settings.json` |
| `figma` | MCP remoto de Figma, viene con el plugin `figma@claude-plugins-official` | Encendido (pide autenticación con `/mcp`) | Plugin |
| `blender-ahujasid` | [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp) (paquete `mcp-for-blender`) | Apagado | `.mcp.json` + `.claude/settings.local.json` |
| `robloxstudio-runtime` | [`@chrrxs/robloxstudio-mcp`](https://www.npmjs.com/package/@chrrxs/robloxstudio-mcp) 3.2.0, para depurar el juego en ejecución | Apagado | `.mcp.json` + `.claude/settings.local.json` |

## El MCP oficial de Studio

Fuente: [Connect to the Roblox Studio MCP server](https://create.roblox.com/docs/studio/mcp) (verificado el 2026-10-11).

**Encenderlo en Studio:** Assistant → **…** → **Manage MCP Servers** → **Enable Studio as MCP server**.
El indicador verde muestra cuántos clientes están conectados.

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

**Herramientas** (26, según la documentación):

| Grupo | Herramientas | Permiso en este repo |
|---|---|---|
| Scripts | `script_read`, `script_search`, `script_grep` · `multi_edit` | lectura: permitidas · `multi_edit`: pregunta |
| Generación | `generate_mesh`, `generate_material`, `generate_procedural_model`, `wait_job_finished`, `search_asset`, `insert_asset`, `upload_image`, `store_image` | `generate_*`, `insert_asset`, `upload_image`, `store_image`: preguntan |
| DataModel | `search_game_tree`, `inspect_instance`, `subagent` | lectura: permitidas |
| Luau | `execute_luau` (pide `datamodel_type`: Edit, Client o Server) | pregunta |
| Playtest | `get_studio_state`, `get_console_output`, `screen_capture` · `start_stop_play` | lectura: permitidas · `start_stop_play`: pregunta |
| Entrada | `character_navigation`, `user_keyboard_input`, `user_mouse_input` | pregunta (por defecto) |
| Documentación | `http_get`, `skill` | pregunta (por defecto) |
| Sesión | `list_roblox_studios` | permitida |

Todas las llamadas necesitan un `studio_id`: empieza por `list_roblox_studios`.

## Reglas

1. **Un solo servidor MCP de Studio a la vez.** Dos plugins haciendo long-polling contra el mismo Studio se bloquean. Si enciendes `robloxstudio-runtime`, apaga `Roblox_Studio` durante esa sesión.
2. **Revisa el interruptor después de cada actualización de Studio.** Hay un fallo reportado (junio de 2026, sin respuesta) en el que "Enable Studio as MCP server" se apaga solo al actualizar.
3. **Desconexiones conocidas cada 5–15 minutos** (reportadas en julio de 2026). Lo único que funciona es apagar y volver a encender el interruptor en Studio. Es normal: no gastes tiempo investigando.
4. **`execute_luau` no ve el juego en ejecución.** Corre en el DataModel del plugin, aislado del juego. Para leer estado vivo, imprime desde el código del juego y léelo con `get_console_output`, o usa `robloxstudio-runtime`.
5. **Llama a `get_studio_state` en cada cambio de etapa** en vez de suponer si Studio está en Edit o en Play.
6. **Los subagentes nunca escriben en Studio.** El setup añade `mcp__Roblox_Studio` y `mcp__robloxstudio-runtime` a `disallowedTools` de los agentes de SyphoDev.
7. Un "Target is not reachable" justo después de actualizar Studio suele ser una regresión de Roblox: revisa el foro de bugs de Studio.

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
- perfiles de CPU y memoria.

Con `--auto-install-plugin` instala su propio plugin en Studio. Tiene herramientas que escriben (`execute_luau`, `set_properties`, `insert_asset`, `manage_monetization`). Usa la versión fijada (3.2.0) y revisa su changelog antes de subirla.

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
