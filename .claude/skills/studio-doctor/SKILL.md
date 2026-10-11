---
name: studio-doctor
description: Diagnostica y arregla la conexión entre Claude Code, el MCP de Roblox Studio, Rojo y las skills. Úsala cuando falle o no aparezca el MCP de Studio (Roblox_Studio), cuando una herramienta de Studio responda "Target is not reachable", cuando list_roblox_studios no vea Studio, cuando Rojo no conecte o los cambios del disco no lleguen a Studio, cuando aparezcan módulos o scripts duplicados, cuando una skill diga que falta LOCAL.md o un programa, después de actualizar Studio, y siempre en una máquina nueva o recién clonada. También cuando el usuario diga "no conecta", "el MCP se cayó", "Rojo no sincroniza" o "algo del setup falla".
---

# studio-doctor

Casi todos los fallos de este estudio caen en uno de tres sitios: la máquina (falta
un programa o una skill), el MCP de Studio (interruptor apagado, desconexión,
dos servidores) o Rojo (sin conectar, dos conexiones, build viejo). Ve de fuera hacia
dentro y **para en cuanto encuentres la causa**: arreglar algo que no estaba roto
añade ruido.

## 1. La máquina

```bash
python scripts/doctor.py
```

Lee la tabla. Cualquier fila ❌ se arregla primero, con el comando de su columna
"Cómo arreglarlo". Para skills o agentes que faltan, vuelve a ejecutar el setup
(`scripts/setup.ps1` o `scripts/setup.sh`). Si una skill de SyphoDev pide su
`LOCAL.md`, la solución es `/roblox-skills-setup`, no editar el archivo a mano.

## 2. El MCP de Studio

1. Llama a `list_roblox_studios`.
   - **Error o herramienta inexistente** → el cliente no tiene el servidor. Revisa:
     - `/mcp` en Claude Code: `Roblox_Studio` debe aparecer conectado.
     - Si sale "pending approval", acepta la confianza de la carpeta: `.claude/settings.json` lo aprueba con `enabledMcpjsonServers`.
     - En macOS, el setup lo registra en scope local (`claude mcp list` debe mostrarlo).
   - **Lista vacía** → Studio no está expuesto. Pide al usuario abrir Studio y comprobar
     Assistant → … → Manage MCP Servers → **Enable Studio as MCP server**, con el
     indicador verde. **Este interruptor se apaga solo tras algunas actualizaciones de
     Studio**: es lo primero que hay que mirar después de actualizar.
   - **Una o varias instancias** → anota el `studio_id` correcto (todas las llamadas lo piden).
2. Llama a `get_studio_state` con ese `studio_id` para saber si está en Edit o en Play.
3. Si las llamadas empiezan a fallar tras unos minutos de funcionar: hay desconexiones
   conocidas cada 5–15 minutos. El arreglo reportado es **apagar y volver a encender**
   "Enable Studio as MCP server" en Studio. No cuesta nada: hazlo antes de investigar más.
4. **Un solo servidor de Studio a la vez.**
   - Si `robloxstudio-runtime` está encendido, `Roblox_Studio` debería estar apagado durante esa sesión.
   - Dos plugins de MCP haciendo long-polling contra el mismo Studio se bloquean entre sí.
   - Revisa `.claude/settings.local.json` y `/mcp`.
5. Si sigue fallando: cierra y vuelve a abrir Studio **y** el cliente (Claude Code).
   `list_roblox_studios` que ve una instancia de menos se arregla así.
6. "Target is not reachable" justo después de actualizar Studio suele ser una regresión
   de Roblox, no tu código: busca en el foro de bugs de Studio antes de gastar tiempo.

Recuerda al diagnosticar: `execute_luau` corre en el DataModel del plugin, aislado del
juego en ejecución. Que no "vea" el estado del servidor durante Play no es un fallo.
Para leer el juego vivo: imprime desde el código del juego y léelo con
`get_console_output`, o enciende `robloxstudio-runtime` (ver `docs/mcp.md`).

## 3. Rojo

1. Dentro del juego: `rojo serve` debe estar corriendo, y **una sola vez**.
2. En Studio, el plugin de Rojo debe estar conectado a ese puerto. Si Studio muestra el
   aviso de conexión ("connect"/"accept"), hay que **aceptarlo**: sin eso no sincroniza nada.
3. **Una sola conexión.** Dos conexiones de Rojo duplican cada script y módulo, y los
   controladores se inicializan dos veces. Si ves duplicados, desconecta todo, cierra
   los `rojo serve` sobrantes y conecta una vez.
4. Comprueba la **marca de build** (build stamp): los scripts de arranque del proyecto
   de SyphoDev la imprimen en Output al dar Play (léela con `get_console_output`). Si
   no aparece, o no refleja el último cambio, Studio corre código viejo: Rojo no está
   sincronizando.
5. Rojo borra lo que no está en el disco. Los hijos creados en tiempo de ejecución o a
   mano en Studio bajo una carpeta gestionada desaparecen al sincronizar; es lo esperado
   ("el disco es la verdad").
6. Script Sync de Studio debe estar **apagado**: compite con Rojo por los mismos scripts.

## 4. Si nada funciona

Abre `docs/troubleshooting.md` (tabla de fallos conocidos con fechas) y
`~/.claude/skills/create-roblox-game/references/mcp.md` (investigación de SyphoDev
sobre el MCP). Resume al usuario qué comprobaste, qué resultado dio cada paso y cuál es
el siguiente paso manual que le toca.
