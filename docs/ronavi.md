# RoNavi Studio

RoNavi Studio es la interfaz de terminal (TUI) de este estudio y su **punto de entrada único**:
instalación inicial, creación de juegos, skills, herramientas, integraciones y continuar proyectos.
Su mascota es **Navi**, un zorro con bufanda roja.

```powershell
.\ronavi          # Windows (cmd o PowerShell), desde la raíz del estudio
```
```bash
sh ronavi.sh      # macOS / Linux
```

La primera vez, el lanzador crea `.venv/` en el estudio e instala Textual ahí (nunca en tu Python).
Después arranca en un par de segundos. Desde *Configuración → Añadir 'ronavi' al PATH* puedes
escribir `ronavi` en cualquier terminal.

## Secciones

| Tecla | Sección | Qué hace |
|---|---|---|
| 1 | Inicio | Estado del entorno, juegos recientes, **Continuar** el último juego |
| 2 | Proyectos | Lista de juegos; **Enter** abre Claude Code en el juego. Carpeta, VS Code, `rokit install`, `wally install`, `check.py`, `rojo serve`, adoptar carpetas, reinstalar el guardián |
| 3 | Nuevo juego | Nombre, género, idea; git propio, commit inicial, código con `roblox-code` y abrir Claude con la etapa 1 |
| 4 | Skills | Inventario de `skills.lock.json`; instalar/sincronizar, buscar actualizaciones, `/roblox-skills-setup` |
| 5 | Herramientas | Diagnóstico completo (`scripts/doctor.py`); instalar programas con winget; dependencias de Python |
| 6 | Integraciones | Servidores MCP (estudio o cada juego), claves como variables de entorno, Figma, cupos |
| 7 | Configuración | Carpeta de juegos, modo de apertura de Claude, animaciones, PATH, asistente |

Otras teclas: `Ctrl+N` nuevo juego, `F5` recargar, `?` ayuda, `Ctrl+P` paleta, `Ctrl+Q` salir.

## Primera ejecución: el asistente

Detecta qué falta y lo arregla reutilizando los scripts del estudio. Lo que ya está bien no se repite.

| Paso | Cómo | Script |
|---|---|---|
| Programas | En la terminal (winget pide aceptar cada licencia) | `scripts/install-prereqs.ps1` |
| Rokit | Automático, si falta `~/.rokit/bin` | `rokit self-install` |
| Sesión de Claude Code | Se abre `claude`: inicias sesión y `/exit` | — |
| Skills y plugins | Automático, con registro en vivo | `scripts/skills_sync.py vendor · user · project · plugins · local-settings` |
| Dependencias de Python | Automático | `pip install --user -r requirements.txt` |
| Carpeta de juegos | Un clic (pide confirmación) | `ROBLOX_GAMES_HOME` de usuario |
| Roblox Studio y servicios | Manual: lo marcas como hecho | Interruptor del MCP, Script Sync apagado, Figma, `LOCAL.md` |

Los pasos manuales son solo los indispensables: iniciar sesión, autorizar Figma y los interruptores
de Studio. En macOS/Linux los programas se instalan con tu gestor de paquetes; RoNavi los comprueba.

## Cada juego es independiente

`games/<Juego>/` (o la carpeta de juegos que elijas) contiene:

| Archivo | Versionado en el git del juego | Qué es |
|---|---|---|
| `.git/` | — | Repositorio propio. RoNavi nunca ejecuta git en un juego cuyo repositorio sea otro |
| `.ronavi/project.json` | sí | Nombre, género, idea, fecha (sin rutas absolutas) |
| `CLAUDE.md` | sí | Instrucciones para Claude Code. RoNavi solo gestiona el bloque entre `<!-- ronavi:begin -->` y `<!-- ronavi:end -->` |
| `.claude/settings.json` | sí | Permisos, MCP aprobados y plugins (copiados del estudio sin borrar los tuyos) |
| `.mcp.json` | sí | El MCP oficial de Roblox Studio |
| `.claude/hooks/ronavi_guard.py` | sí | El guardián (se actualiza al sincronizar) |
| `.claude/settings.local.json` | no | Hook del guardián y reglas `deny` con rutas absolutas de esta máquina |
| `.claude/ronavi-guard.json` | no | Zonas protegidas de esta máquina |
| `README.md`, `.gitignore` | sí | Se crean o completan; nunca se reemplaza lo tuyo |

**Abrir Claude Code** en un juego ejecuta `claude --add-dir <estudio>` con el juego como carpeta de
trabajo. `--add-dir` hace visibles las skills del estudio (`.claude/skills/`) y sus documentos
(por ejemplo `docs/quotas.md`), que el juego necesita: como cada juego es su propio repositorio,
Claude Code no buscaría skills más arriba. Antes de abrir, RoNavi vuelve a comprobar el git del juego
y reinstala su guardián.

Variables que recibe Claude: `ROBLOX_GAMES_HOME` (la carpeta de juegos), `RONAVI_STUDIO` y `RONAVI_GAME`.

## Protecciones

Defensa en capas contra que Claude, una skill o un script toquen otro juego o la plantilla:

1. **Comprobación de rutas en RoNavi** (`ronavi/core/guard.py`). Toda escritura de RoNavi en un juego
   pasa por `GameScope`: la ruta, con enlaces simbólicos y *junctions* resueltos, debe quedar dentro
   del juego. Un juego es siempre un hijo directo de la carpeta de juegos, nunca el estudio ni la
   propia carpeta de juegos. Los nombres se validan (sin `..`, separadores, acentos ni nombres
   reservados de Windows).
2. **Git aislado.** Antes de cualquier operación git, RoNavi exige que `git rev-parse --show-toplevel`
   sea el propio juego. Sin su `.git`, git subiría al repositorio del estudio.
3. **Guardián `PreToolUse`** en cada juego. Bloquea (código de salida 2, con el motivo para Claude):
   - `Write`, `Edit`, `MultiEdit` y `NotebookEdit` fuera del juego que caigan en la plantilla o en otro juego;
   - comandos de Bash o PowerShell que cambian archivos (`rm`, `mv`, `cp`, `>`, `sed -i`, `Remove-Item`,
     `Set-Content`, `git commit`…) y nombran una ruta de esas zonas, también en formato Git Bash (`/c/...`);
   - ediciones del propio guardián.

   Leer nunca se bloquea. `work/` del estudio (registro de cupos) y todo lo que está fuera del estudio
   (por ejemplo `~/.claude/skills/*/LOCAL.md`) sigue permitido.
4. **Reglas `deny` de Edit** con rutas absolutas para cada entrada de la plantilla y cada juego hermano,
   en el `settings.local.json` del juego. Se regeneran al crear un juego y al abrir cualquiera.
5. **Confirmaciones** antes de instalar, cambiar variables de entorno, adoptar carpetas o cambiar el
   PATH. Las claves se escriben en el registro de usuario de Windows: nunca en archivos ni en pantalla.

**Límites conocidos.** El guardián analiza el texto del comando: no ve lo que hace por dentro un
script de Python o Node que abre archivos por su cuenta, ni rutas construidas con variables. Para un
aislamiento a nivel de sistema operativo, activa el [sandbox de Claude Code](https://code.claude.com/docs/en/sandboxing).
Las reglas `deny` y el hook no se aplican a lo que hagas tú a mano.

## Línea de comandos

Sin argumentos abre la TUI. Los subcomandos sirven para scripts y pruebas:

```text
ronavi list                                   juegos y estado del guardián
ronavi new "Coin Dash" --genre obby --desc "…" [--no-git] [--no-commit] [--code]
ronavi open CoinDash [--window] [--prompt "…"]
ronavi sync-guards                            reinstala el guardián de todos los juegos
ronavi doctor [--json]                        lo mismo que python scripts/doctor.py
ronavi paths                                  rutas que usa RoNavi
```

## Código y pruebas

```text
ronavi/
  bootstrap.py        venv + dependencias (solo biblioteca estándar)
  cli.py              subcomandos
  core/               lógica sin interfaz: paths, guard, projects, environment, integrations, skills, launcher
  assets/ronavi_guard.py   el hook que se copia a cada juego
  ui/                 Textual: app, welcome, wizard, main (secciones), modals, mascot, styles.tcss
tests/                unittest: guard, proyectos y aislamiento, hook, integraciones, TUI (pilot de Textual)
```

```powershell
.venv\Scripts\python -m unittest discover -s tests -t .   # todas, con la TUI
python scripts\validate.py                                # lo mismo que la CI
```

Las pruebas crean un estudio temporal con su propio git y comprueban, entre otras cosas, que crear
un juego no cambia ni un byte de la plantilla ni del resto de juegos, que el hook instalado bloquea
escrituras en un juego hermano y que una *junction* dentro de un juego no sirve para salir de él.

## Problemas frecuentes

| Síntoma | Arreglo |
|---|---|
| `ronavi` no se reconoce | Ejecuta `.\ronavi` desde la raíz del estudio o añádelo al PATH en Configuración |
| "No se pudo preparar el entorno de RoNavi" | Borra `.venv/` y vuelve a ejecutar; pip necesita internet la primera vez |
| Caracteres raros o sin colores | Usa Windows Terminal (o cualquier terminal con color verdadero) y una fuente con bloques Unicode |
| Claude dice que el guardián lo bloqueó | Es lo esperado fuera del juego: haz ese cambio tú o desde RoNavi |
| El guardián no aparece en un juego clonado de otro PC | Proyectos → **Guardián** (o `ronavi sync-guards`): `settings.local.json` es propio de cada máquina |
