# Registro de decisiones

Cada entrada: qué se decidió, por qué, y qué se descartó. Las diferencias entre el
encargo original y la documentación oficial están al final, con fecha de verificación.

## D1. Rojo en vez de Script Sync

**Decisión:** el código vive en disco y llega a Studio con Rojo. Script Sync de Studio queda apagado.

**Por qué:**
- La regla 1 de `roblox-code` es que el disco es la única verdad: el proyecto v1 de SyphoDev murió por la deriva entre Studio y disco.
- Rojo permite las 4 revisiones sin Studio (`rojo build`, `lune`, `selene`, `stylua`), los commits de git y el `sourcemap.json` para luau-lsp.
- Script Sync y Rojo compiten por los mismos scripts.

## D2. Knit está archivado, pero se mantiene en los juegos de SyphoDev

**Decisión:** los juegos nuevos usan el scaffold de `new_project.py` tal cual (Knit 1.7.0 + Promise + Signal + Trove) y no se mezcla otro framework.

**Por qué:**
- Knit está archivado: no recibirá cambios, pero funciona.
- Las skills, las revisiones y los ejemplos de SyphoDev dan por hecho ese layout.
- En `roblox-code`, Knit es solo ciclo de vida e inyección de dependencias; la red pasa por un único `Net.luau`, así que la dependencia es pequeña.
- Cambiar de framework a medio juego cuesta más que convivir con uno archivado.

## D3. Un solo servidor MCP de Studio a la vez

**Decisión:** `Roblox_Studio` (oficial) encendido; `robloxstudio-runtime` apagado y solo para depurar en vivo, apagando el oficial durante esa sesión. Los subagentes no tienen acceso a ninguno de los dos.

**Por qué:**
- Dos plugins haciendo long-polling contra el mismo Studio se bloquean, con el mismo patrón de fallo que dos conexiones de Rojo.
- Un solo hilo que escribe en Studio evita carreras entre agentes paralelos.

## D4. EL4CTEO en lugar del núcleo de roblox-brain

**Decisión:**
- El conocimiento general de Roblox (Luau, red, seguridad, datos, MCP…) viene del plugin `roblox-skills` de EL4CTEO.
- De roblox-brain solo se usan `roblox-game-design` y `roblox-player-psychology`.

**Por qué:**
- Los dos paquetes cubren lo mismo en el núcleo; cargar ambos duplicaría contexto y daría consejos contradictorios.
- EL4CTEO comprueba con CI el tipado de cada ejemplo Luau contra la API (Studio 0.740, septiembre de 2026), se instala como plugin y es MIT.
- Las dos skills de diseño de roblox-brain no tienen equivalente en EL4CTEO.

## D5. Hi3DGen en lugar de Hunyuan3D y TRELLIS.2

**Decisión:** imagen → 3D con Hi3DGen en Kaggle (Space de Hugging Face como respaldo).

**Por qué:**
- Hi3DGen es MIT, sin cláusula territorial, y es lo que el pipeline de SyphoDev mide y prueba (~102 s de GPU por modelo).
- Las licencias de Tencent Hunyuan no aplican en la UE, el Reino Unido ni Corea del Sur, y prohíben usar el *output* allí.
- TRELLIS.2 (MIT) queda como alternativa documentada si Hi3DGen desaparece, pero hoy no está integrado en los scripts.

## D6. Meshy y Tripo descartados

**Decisión:** no se usan servicios comerciales de generación 3D.

**Por qué:**
- La plantilla se basa en cupos gratis renovables (Kaggle, ZeroGPU, Cloudflare).
- Los niveles gratis de Meshy y Tripo dan pocos créditos al mes y condicionan la licencia del resultado al plan de pago (en el gratis, los modelos suelen ser públicos o de licencia restringida). Esto no se volvió a verificar el 2026-10-11: revísalo en sus páginas de precios si reconsideras la decisión.
- Hi3DGen + Blender sin ventana da control total de topología, UV y presupuesto de triángulos.

## D7. Skills de SyphoDev a nivel usuario y parche de agentes

**Decisión:** SyphoDev se instala en `~/.claude/skills` y `~/.claude/agents` con su propio instalador. Después, el setup añade `mcp__Roblox_Studio, mcp__robloxstudio-runtime` a `disallowedTools` de sus 7 agentes, sin quitar lo que ya tenían.

**Por qué:**
- Sus scripts usan rutas `~/.claude/skills/...` y su instalador respeta los `LOCAL.md`.
- Sus agentes solo bloqueaban `mcp__robloxstudio-mcp`, el nombre del servidor de terceros. El servidor oficial se llama `Roblox_Studio`.
- Formato verificado en la documentación de subagentes: cadena separada por comas o lista YAML; `mcp__<servidor>` quita todas las herramientas de ese servidor.
- El instalador de SyphoDev hace copia de respaldo en **cada** ejecución. Para que el setup sea idempotente, solo se ejecuta si el contenido instalado difiere del fijado (se compara por hash).

## D8. Lógica del setup en un solo ayudante Python

**Decisión:** `scripts/setup.ps1` y `scripts/setup.sh` son envoltorios finos y la lógica vive en `scripts/skills_sync.py`.

**Por qué:**
- Una sola implementación para Windows, macOS y Linux: clonado, checkout, hashes, parche de agentes, plugins y actualización.
- Python ya es obligatorio. Solo se usa la biblioteca estándar.

## D9. Servidores MCP opcionales apagados en `settings.local.json`

**Decisión:** `.claude/settings.json` (compartido) solo aprueba `Roblox_Studio`. El setup escribe `disabledMcpjsonServers: ["blender-ahujasid", "robloxstudio-runtime"]` en `.claude/settings.local.json` (no versionado). Ese archivo solo se siembra con nombres que no aparezcan ya en ninguna de las dos listas, así que las elecciones del usuario se respetan.

**Por qué:**
- Según la referencia de settings, una entrada en `disabledMcpjsonServers` **en cualquier archivo** rechaza el servidor y gana sobre `enabledMcpjsonServers`.
- Con la lista en el archivo compartido, encender Blender obligaría a editar un archivo versionado.

## D10. Servidor de Blender llamado `blender-ahujasid`

**Decisión:** el servidor del proyecto se llama `blender-ahujasid`, no `blender`.

**Por qué:**
- En la máquina original ya había otro servidor MCP `blender` (distinto) a nivel usuario.
- Dos scopes con el mismo nombre y distinto comando provocan avisos de conflicto y ambigüedad sobre cuál se carga.

## D11. Rokit lee el `aftman.toml` de los juegos

**Decisión:** se instala Rokit y se usa `rokit install` donde las skills de SyphoDev dicen `aftman install`.

**Por qué:**
- Rokit es compatible con Aftman y Foreman, está en winget (`Rojo.Rokit`) y está mantenido.
- No se modifica el generador de SyphoDev.
- La instalación de winget no crea `~/.rokit/bin`, la carpeta de los enlaces a rojo, wally y compañía. Hace falta `rokit self-install`, que también la añade al PATH; el setup lo ejecuta si falta (comprobado el 2026-10-11 con Rokit 1.2.0).

**luau-lsp:** el `aftman.toml` que genera SyphoDev no lo incluye. Se cubre con la extensión de VS Code `JohnnyMorganz.luau-lsp`, que trae su propio binario. Para la CLI en un juego: `rokit add JohnnyMorganz/luau-lsp`.

## D12. Permisos

**Decisión:**
- `permissions.allow` lleva las herramientas de Studio de solo lectura y los comandos de revisión, con formas `Bash(...)` y `PowerShell(...)`.
- Todo lo que escribe en Studio o gasta cupo va en `permissions.ask`, para que pregunte incluso en modos permisivos.
- `permissions.deny` bloquea `Read(.env*)`, `Read(**/kaggle.json)` y `Read(~/.kaggle/**)`.

**Límite conocido:** una regla `Read` bloquea la herramienta Read, no un `cat .env` por Bash. La defensa real es no tener secretos en archivos: van en variables de entorno.

## D13. RoNavi Studio: TUI en Python con Textual

**Decisión:** la interfaz es una TUI de pantalla completa en Python 3.11+ con [Textual](https://textual.textualize.io/) 8.2.8, dentro de `ronavi/`. Se lanza con `ronavi.cmd` (Windows) o `ronavi.sh` (macOS/Linux), que crean `.venv/` en el estudio la primera vez.

**Por qué:**
- Python ya es obligatorio y toda la lógica existente (`doctor.py`, `skills_sync.py`) es Python: RoNavi la **importa** en vez de duplicarla.
- Textual funciona en Windows Terminal, macOS y Linux, tiene temas, tablas, formularios y un *pilot* para probar la interfaz sin terminal.
- El venv propio evita tocar el Python del usuario; el lanzador reinstala solo si cambia `ronavi/requirements.txt` (hash).
- Descartados: Go/Bubble Tea o Rust/Ratatui (otro lenguaje y otra toolchain que instalar) e Ink/Node (Node es opcional en este estudio).

**Mascota:** Navi se dibuja con medios bloques Unicode (`▀` con color de frente y de fondo, dos píxeles por celda). Se ve nítida con cualquier fuente, no necesita imágenes y ocupa unos cientos de celdas.

## D14. Juegos aislados en tres capas

**Decisión:** cada juego tiene su git, su `CLAUDE.md` y su `.claude/`. Las escrituras se protegen con (1) `GameScope` en RoNavi, (2) un hook `PreToolUse` copiado en cada juego (`.claude/hooks/ronavi_guard.py`) y (3) reglas `deny` de Edit con rutas absolutas para la plantilla y los juegos hermanos.

**Por qué:**
- Las reglas `deny` siempre ganan a `allow`. Con los juegos dentro de `games/` del estudio, una regla para todo el estudio bloquearía también el propio juego. Por eso se listan las entradas de la plantilla y los hermanos uno por uno, y se regeneran al crear o abrir un juego.
- Un hook que sale con código 2 bloquea la llamada antes de evaluar los permisos, incluso en modos permisivos, y su mensaje llega a Claude. Cubre también lo añadido después de la última sincronización y los comandos de Bash/PowerShell.
- El hook y las reglas absolutas viven en `.claude/settings.local.json` (no versionado): las rutas son de esta máquina. `settings.local.json` se carga desde la raíz del repositorio git, que es el propio juego.
- El hook usa la forma *exec* (`command` + `args`) con el Python base del venv: no depende de que Git Bash o PowerShell interpreten comillas.
- Si el guardián falla por un error interno, deja pasar la acción y lo avisa por stderr: un guardián roto no debe dejar inservible la sesión.

## D15. Claude Code se abre con `--add-dir <estudio>`

**Decisión:** RoNavi abre Claude Code con el juego como carpeta de trabajo y `--add-dir` hacia el estudio.

**Por qué:**
- Claude Code busca `.claude/skills/` hacia arriba **solo hasta la raíz del repositorio git**, y cada juego es su propio repositorio: sin `--add-dir`, el juego no vería `quota-guard`, `own-audio`, `studio-doctor` ni las skills de terceros.
- Los scripts de esas skills calculan la raíz del estudio desde su propia ruta (`parents[4]`): copiarlas a cada juego rompería `docs/quotas.md` y el registro de cupos compartido de `work/`.
- `--add-dir` da acceso de lectura y escritura al estudio; la escritura la cortan el hook y las reglas `deny` (D14). `work/` sigue permitido.

## D16. Claves desde la TUI solo como variables de entorno de usuario

**Decisión:** en Windows, *Integraciones → Definir valor…* guarda la clave en `HKCU\Environment` (como `setx`, sin su corte de 1024 caracteres) y avisa al sistema del cambio. En macOS/Linux, RoNavi muestra el `export` que debes añadir.

**Por qué:** mantiene la regla del estudio (las claves viven solo en variables de entorno) y evita pasos manuales. El valor no se escribe en archivos, no se muestra y no pasa por Claude. RoNavi solo informa "configurada" o "falta".

## D17. Ideas antes que juegos, en `work/ideas/`

**Decisión:** *Explorar idea* crea `work/ideas/<fecha>/` con un `CLAUDE.md` propio, `.claude/settings.json` del estudio y el mismo guardián que un juego, pero más estrecho: Claude solo escribe dentro de esa idea y en el registro de `quota-guard` (`work/quota-ledger.json`), no en otras ideas. No hay git ni proyecto de Rojo. Al crear un juego *basado en idea*, sus notas (sin los archivos de RoNavi ni los ocultos) se copian a `docs/research/` del juego, que guarda `from_idea` en `.ronavi/project.json`. La idea no se borra.

**Por qué:** investigar no debería obligar a inventar un nombre y un género. `work/` ya está fuera del git del estudio y de las reglas deny (D14), así que una idea no ensucia la plantilla ni aparece como juego en `games/`. `GameScope` acepta otra carpeta padre (`container`) y `install_guard` es el mismo para juegos e ideas: una sola implementación de las protecciones.

## D18. El clon es la instalación; las versiones son tags

**Decisión:** `install.ps1` / `install.sh` (una línea con `irm | iex` o `curl | sh`) clonan el estudio en `RONAVI_HOME` (por defecto `~/RoNavi`), hacen checkout del tag `vX.Y.Z` más nuevo y ponen `ronavi` en el PATH. `ronavi update` pasa al tag más nuevo, o hace `git pull --ff-only` si el estudio está en una rama, y se niega con cambios sin guardar. La versión vive en `ronavi/__init__.py`; el workflow `release` comprueba que el tag coincide, pasa las revisiones y crea la GitHub Release con las notas de `CHANGELOG.md`.

**Por qué:** RoNavi depende de todo el estudio (skills, `scripts/`, `.claude/`, `docs/`), no solo de su código Python; un paquete de PyPI tendría que descargar el estudio aparte y mantener dos versiones sincronizadas. Con el clon hay una sola fuente de verdad, actualizar es git, y los juegos (`games/`) e ideas (`work/`) quedan fuera porque git los ignora.

---

## Diferencias entre el encargo y la documentación oficial

Verificado el 2026-10-11.

| Tema | El encargo decía | La documentación dice | Qué se hizo |
|---|---|---|---|
| Paquete de blender-mcp | `uvx blender-mcp` | El paquete de PyPI ahora es `mcp-for-blender`; `blender-mcp` 2.0.0 es un alias ([README](https://github.com/ahujasid/blender-mcp)) | `cmd /c uvx --python 3.11 mcp-for-blender` |
| Fijar el plugin de EL4CTEO a un commit | Fijar a `11571e0` "si la documentación lo permite" | Un marketplace solo se fija a **rama o tag** (`#ref`, `"ref"`); `sha` existe solo para fuentes de plugins ([plugin marketplaces](https://code.claude.com/docs/en/plugins/marketplace-reference)) | Fijado al tag **`v1.1.0`**, que apunta exactamente a `11571e0`. Setup y doctor comprueban que el contenido instalado coincide con ese commit. |
| `disabledMcpjsonServers` en `.claude/settings.json` | Ahí | Rechaza desde cualquier archivo y no se puede revertir localmente ([settings](https://code.claude.com/docs/en/settings-reference)) | Va en `.claude/settings.local.json` (D9) |
| Config de Studio en macOS | `/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP` | Confirmado ([Studio MCP](https://create.roblox.com/docs/studio/mcp)) | `setup.sh` lo registra en scope local |
| Figma Starter | 20 llamadas al mes | 20/mes es para asientos **View/Collab** en cualquier plan; Education = 200/día y 10/min, como Dev/Full en Professional ([rate limits](https://developers.figma.com/docs/figma-mcp-server/rate-limits-access/)) | `docs/quotas.md` con las dos filas |
| HF ZeroGPU | ~300 s al día | 5 min/día con cuenta gratis (2 min sin sesión); se reinicia 24 h después del primer uso ([ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu)) | Igual en cifra, regla de reinicio corregida |
| Cupo de audio de Open Cloud | "verificar" | Contradicción oficial: 100/mes verificados en la [guía de Open Cloud](https://create.roblox.com/docs/cloud/guides/usage-assets) contra 2.000 cada 30 días en la [página de audio](https://create.roblox.com/docs/en-us/audio/assets) | Se usa 100 (conservador) |
| Gemini CLI | 1.000 solicitudes al día | "Gemini CLI was replaced by Antigravity CLI on June 18th, 2026" para el nivel gratuito ([cuotas](https://geminicli.com/docs/resources/quota-and-pricing/)) | Listado como respaldo **no verificado** |
| Kaggle | Cuota semanal | Sin cifra oficial ni día de reinicio publicado; los informes dicen ~30 h y sábado o domingo | Ventana móvil de 7 días en `quota-guard` |
| Procedurales de Studio | 50 en 24 h | Confirmado: 50 en ventana móvil de 24 h ([Assistant](https://create.roblox.com/docs/en-us/assistant/guide)) | Sin cambios |
| Cloudflare | 10.000 neurons/día, 00:00 UTC | Confirmado ([precios](https://developers.cloudflare.com/workers-ai/platform/pricing/)). SyphoDev midió 141 neurons por imagen de 1024 px con 4 pasos; la tabla de precios da ~58. | Se usa la medición (conservadora) |
| Triángulos | menos de 20.000 | 20.000 es el tope duro por MeshPart; SyphoDev recomienda menos de 10.000 | Documentados los dos |
| Instalación de plugins desde el shell | `claude plugin` | `claude plugin marketplace add <owner/repo#ref>` y `claude plugin install <id> --scope project` | Usado en el setup. Instalar con `--scope project` reescribe `.claude/settings.json` (mismas claves, otro orden). |
