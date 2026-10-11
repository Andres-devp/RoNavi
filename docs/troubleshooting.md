# Solución de problemas

Empieza siempre por `python scripts/doctor.py` y, dentro de Claude Code, por la skill
`studio-doctor`. Esta página es la referencia completa.

## MCP de Studio: fallos conocidos

Tabla basada en la investigación de SyphoDev (`create-roblox-game/references/mcp.md`,
fechada el 2026-08-30) y en el foro de bugs de Studio.

| Fallo | Estado | Qué hacer |
|---|---|---|
| "Enable Studio as MCP server" se apaga solo tras actualizar Studio (reportado 4 jun 2026) | **Abierto** | Revisa el interruptor después de cada actualización |
| La conexión se cae cada 5–15 minutos (reportado 4–9 jul 2026) | **Abierto** | Apaga y vuelve a encender el MCP en Studio. Cuenta con ello. |
| Herramientas de Play devuelven "Target is not reachable" (22 may 2026) | Arreglado el 27 may | Actualiza Studio |
| `get_console_output` devolvía logs de Studio y plugins en vez del juego (30 may 2026) | Arreglado el 1 jun | Actualiza Studio |
| El MCP no podía iniciar ningún modo de ejecución (20 ago 2026) | Arreglado el 24 ago | Actualiza Studio |
| `list_roblox_studios` ve una instancia de menos, o ninguna | Intermitente | Cierra y abre Studio y el cliente |
| Dos servidores MCP conectados al mismo Studio | Por diseño | Deja solo uno (ver `docs/mcp.md`) |
| `execute_luau` no ve el estado del juego en Play | Por diseño | Corre en el DataModel del plugin. Imprime desde el juego y usa `get_console_output`, o `robloxstudio-runtime`. |

Patrón general: casi toda rotura del MCP es una regresión de versión que Roblox arregla
en días. Actualiza Studio antes de una sesión larga y revisa el interruptor.

## Rojo: trampas

| Síntoma | Causa | Arreglo |
|---|---|---|
| Cada script y módulo aparece dos veces; los controladores arrancan dos veces | **Dos conexiones de Rojo** (dos `rojo serve`, o el plugin conectado dos veces) | Desconecta todo, cierra los servidores sobrantes y conecta una sola vez |
| Objetos creados en Studio (o en tiempo de ejecución) dentro de una carpeta gestionada desaparecen | **Rojo borra lo que no está en el disco** | Es lo esperado: el disco es la verdad. Crea esas cosas en el proyecto (`.model.json`, Luau) o fuera de las carpetas de Rojo. |
| El plugin dice conectado pero no llega ningún cambio | **El aviso de conexión no se aceptó** | En Studio, abre el panel de Rojo y pulsa Connect / Accept. Una conexión TCP no es una sesión sincronizada. |
| La marca de build no aparece en Output al dar Play | Studio corre código viejo | Rojo no sincroniza: revisa las tres filas anteriores |
| Cambios hechos en Studio que "vuelven atrás" | Script Sync de Studio encendido, o se editó en Studio | Apaga Script Sync; edita siempre en disco |
| `rojo` no se encuentra dentro del juego | Falta `rokit install` en esa carpeta, o falta `~/.rokit/bin` | `rokit install` (lee el `aftman.toml` del juego). Si Rokit vino de winget, ejecuta antes `rokit self-install` (el setup lo hace) y abre una terminal nueva. |

## Windows: `uvx` o `npx` dan `ENOENT`

Claude Code lanza el servidor sin shell, y en Windows `npx` es un `.cmd`. Envuelve el
comando en `cmd /c`, como ya hace `.mcp.json`:

```json
"command": "cmd", "args": ["/c", "uvx", "mcp-for-blender"]
```

Si `uvx` no se encuentra después de instalar uv, abre una terminal nueva (el PATH se
actualiza solo en las terminales nuevas) y reinicia Claude Code.

## Kaggle: la GPU no aparece

- La GPU de Kaggle exige **teléfono verificado** en la cuenta: Settings → Phone Verification.
- Sin verificar, los kernels corren sin acelerador y Hi3DGen falla o tarda horas.
- El token va en `KAGGLE_API_TOKEN` o en `~/.kaggle/kaggle.json`. Claude tiene prohibido leer ese archivo (`permissions.deny`).
- La cuota semanal real se ve en kaggle.com → Settings. `quota-guard` lleva una aproximación.

## Figma Education sigue limitando como Starter

Tienes Education con asiento Dev o Full (200 llamadas al día), pero el MCP responde con
el límite bajo:

1. Ejecuta la herramienta `whoami` del MCP de Figma (no gasta cupo) para ver el plan y el asiento.
2. Comprueba que el archivo está en un equipo Education, no en Drafts ni en un equipo Starter. El límite puede depender del equipo dueño del archivo.
3. Reautentica: `/mcp` → figma → desconectar y volver a autenticar.
4. Si persiste, escribe al soporte de Figma con la salida de `whoami` y el texto exacto del error.

## Plugins y skills

| Síntoma | Arreglo |
|---|---|
| `/roblox-skills:...` no aparece | `claude plugin list`; si falta, vuelve a ejecutar el setup. Acepta la confianza de la carpeta. |
| `doctor.py` dice "roblox-skills fijado: differs" | El marketplace no está en `v1.1.0`: vuelve a ejecutar el setup, que lo refija |
| Una skill de SyphoDev pide `LOCAL.md` | `/roblox-skills-setup` en Claude Code |
| Un agente de SyphoDev intentó usar Studio | Vuelve a ejecutar el setup (reaplica el parche de `disallowedTools`) |
| Aparecen carpetas `~/.claude/skills-backup-*` | Las crea el instalador de SyphoDev al reinstalar. Se pueden borrar a mano cuando ya no hagan falta. |

## Python

- **Python 3.14:** las dependencias se instalaron sin problemas en esta máquina (2026-10-11). Si un paquete no tiene wheel para tu versión, usa Python 3.12.
- **macOS/Linux con "externally-managed-environment" (PEP 668):** mira el mensaje de `setup.sh`. Usa un Python de python.org o pyenv, o `PIP_BREAK_SYSTEM_PACKAGES=1`.
