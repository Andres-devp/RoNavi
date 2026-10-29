# RoNavi Studio

RoNavi Studio es la interfaz de terminal (TUI) de este estudio y su **punto de entrada único**:
instalación inicial, creación de juegos, skills, herramientas, integraciones y continuar proyectos.
Su mascota es **Navi**, un zorro con bufanda roja.

```powershell
irm https://raw.githubusercontent.com/Andres-devp/RoNavi/main/install.ps1 | iex   # instalar (Windows)
```
```bash
curl -fsSL https://raw.githubusercontent.com/Andres-devp/RoNavi/main/install.sh | sh   # macOS / Linux
```

Después, en cualquier terminal y carpeta:

```bash
ronavi
```

El instalador clona el estudio en `RONAVI_HOME` (por defecto `~/RoNavi`) en la última versión
publicada y pone `ronavi` en el PATH de tu usuario (en macOS/Linux, el enlace `~/.local/bin/ronavi`).
Si clonaste a mano, `.\ronavi` (o `sh ronavi.sh`) desde la raíz del estudio funciona igual, y
`ronavi path add` (o el paso del asistente, o *Configuración → Añadir 'ronavi' al PATH*) lo deja
disponible en todas partes.

La primera vez, el lanzador crea `.venv/` en el estudio e instala Textual ahí (nunca en tu Python).
Después arranca en un par de segundos.

## Secciones

| Tecla | Sección | Qué hace |
|---|---|---|
| 1 | Inicio | Estado del entorno, juegos recientes, **Continuar** el último juego |
| 2 | Proyectos | Lista de juegos; **Enter** abre Claude Code en el juego. Carpeta, VS Code, `rokit install`, `wally install`, `check.py`, `rojo serve`, adoptar carpetas, reinstalar el guardián |
| 3 | Ideas | **Explorar idea** sin nombre ni género; lista de ideas, abrirlas en Claude y **Convertir en juego** |
| 4 | Nuevo juego | Nombre, género, idea, *basado en una idea*; git propio, commit inicial, código con `roblox-code` y abrir Claude con la etapa 1 |
| 5 | Skills | Inventario de `skills.lock.json`; instalar/sincronizar, buscar actualizaciones, `/roblox-skills-setup` |
| 6 | Herramientas | Diagnóstico completo (`scripts/doctor.py`); instalar programas con winget; dependencias de Python |
| 7 | Integraciones | Servidores MCP (estudio o cada juego), claves como variables de entorno, Figma, cupos |
| 8 | Configuración | Carpeta de juegos, modo de apertura de Claude, animaciones, PATH, asistente, **Actualizar todo** y **Actualizar RoNavi** |

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
| `ronavi` en cualquier terminal | Un clic (pide confirmación) | PATH de usuario (Windows) o `~/.local/bin/ronavi` |
| Roblox Studio y servicios | Manual: lo marcas como hecho | Interruptor del MCP, Script Sync apagado, Figma, `LOCAL.md` |

Los pasos manuales son solo los indispensables: iniciar sesión, autorizar Figma y los interruptores
de Studio. En macOS/Linux los programas se instalan con tu gestor de paquetes; RoNavi los comprueba.

## Ideas: investigar antes de tener juego

¿Quieres investigar sin decidir nombre, género ni descripción? **Ideas → Explorar idea** (también
desde Inicio, o `ronavi idea`). El campo «¿Qué tienes en mente?» es opcional.

1. RoNavi crea `work/ideas/<fecha>/` (p. ej. `work/ideas/2026-10-29-1530/`): sin git, sin Rojo y fuera
   del git del estudio, con un `CLAUDE.md` que le dice a Claude que solo investigue.
2. Abre Claude Code ahí con un prompt de investigación de mercado: tres conceptos (nombre provisional,
   género, bucle, público, por qué puede funcionar, riesgo) en `IDEA.md`, con fuentes.
3. La idea tiene su propio guardián, más estricto que el de un juego: Claude solo escribe dentro de esa
   idea (y en el registro de cupos). No puede crear `games/<Juego>/` ni tocar otras ideas.
4. Cuando elijas un concepto: **Convertir en juego** (o *Nuevo juego → Basado en una idea*). RoNavi
   propone el título de `IDEA.md` como nombre, crea el juego como siempre y copia la investigación a
   `docs/research/`. El primer prompt le dice a Claude que planifique sobre ella en vez de repetirla.
   La idea se conserva, marcada con el juego que salió de ella.

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

Variables que recibe Claude: `ROBLOX_GAMES_HOME` (la carpeta de juegos), `RONAVI_STUDIO` y `RONAVI_GAME`
(`RONAVI_IDEA` en una idea).

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
ronavi new "Coin Dash" --genre obby --desc "…" [--no-git] [--no-commit] [--code] [--from-idea ID]
ronavi open CoinDash [--window] [--prompt "…"]
ronavi idea [--hint "…"] [--no-open] [--window]  explora una idea sin nombre ni género
ronavi idea 2026-10-29-1530                   reabre una idea en Claude Code
ronavi ideas                                  ideas guardadas
ronavi sync-guards                            reinstala el guardián de todos los juegos
ronavi doctor [--json]                        lo mismo que python scripts/doctor.py
ronavi update [--check]                       pasa a la última versión (o git pull en tu rama)
ronavi update --all                           actualiza todo (ver Versiones y actualizaciones)
ronavi path [add]                             ¿"ronavi" funciona en cualquier terminal? add lo arregla
ronavi paths                                  rutas que usa RoNavi
ronavi --version                              versión y commit de git
```

## Versiones y actualizaciones

El estudio clonado **es** la instalación; no hay paquete aparte (D18). Cada versión es un tag de git
`vX.Y.Z` con su [GitHub Release](https://github.com/Andres-devp/RoNavi/releases) y sus notas en
[CHANGELOG.md](../CHANGELOG.md).

- **Actualizar:** `ronavi update`, *Configuración → Actualizar RoNavi* o volver a ejecutar el instalador.
  Una instalación pasa al tag más nuevo; un clon de desarrollo (en una rama, como `main`) hace
  `git pull --ff-only`. Si el estudio tiene cambios sin guardar en archivos de git, no se toca nada.
  Tus juegos (`games/`), ideas (`work/`) y configuración (`.ronavi/`) están fuera de git y no cambian.
- **Actualizar todo:** `ronavi update --all` o *Configuración → Actualizar todo*. En orden:
  1. **RoNavi**, como arriba.
  2. **Skills de terceros** (`scripts/update-skills`): en la terminal, te pregunta antes de mover cada
     commit fijado.
  3. **Plugins de Claude Code**: `claude plugin marketplace update` y `claude plugin update` de
     `roblox-skills@roblox-skills` y `figma@claude-plugins-official`. El tag fijado de EL4CTEO no se
     mueve; si tu marketplace no está en ese tag, se avisa (*Skills → Instalar / sincronizar* lo arregla).
  4. **Guardianes**: el de cada juego, con sus hooks y reglas nuevos.
  5. **Toolchain de cada juego**: sube las versiones fijadas y ejecuta `rokit install` en los juegos con
     `aftman.toml` o `rokit.toml`.

  Si un paso falla, sigue con el siguiente; al final hay un resumen ✔/✘ por paso (… si quedó pendiente).
  La CLI termina con código 1 si algún paso falló.
- **Aviso:** al arrancar, como mucho una vez al día, RoNavi mira los tags de `origin` (3 s como máximo,
  en silencio si no hay red) y avisa si hay una versión más nueva que la tuya.
- **Publicar una versión** (mantenedores):
  1. Sube `__version__` en `ronavi/__init__.py` y añade su sección `## [X.Y.Z] - fecha` en `CHANGELOG.md`.
  2. Commit, y luego `git tag vX.Y.Z` y `git push origin vX.Y.Z`.
  3. El workflow `release` comprueba que el tag coincide con `__version__`, pasa las mismas revisiones
     que la CI y crea la GitHub Release con las notas del CHANGELOG (`scripts/release_notes.py`).

## Código y pruebas

```text
ronavi/
  bootstrap.py        venv + dependencias (solo biblioteca estándar)
  cli.py              subcomandos
  core/               lógica sin interfaz: paths, guard, projects, ideas, updates, environment, integrations, skills, launcher
  assets/ronavi_guard.py   el hook que se copia a cada juego
  ui/                 Textual: app, welcome, wizard, main (secciones), modals, mascot, styles.tcss
tests/                unittest: guard, proyectos y aislamiento, ideas, actualizaciones, hook, integraciones, TUI (pilot de Textual)
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
| `ronavi` no se reconoce | Abre una terminal **nueva** después de instalar. Si sigue igual: `.\ronavi path add` desde la raíz del estudio (en macOS/Linux, comprueba que `~/.local/bin` está en tu PATH) |
| `ronavi update` dice que hay cambios sin guardar | Has editado archivos del estudio: haz commit o `git stash`, actualiza y luego `git stash pop` |
| El instalador dice que la carpeta ya existe | Esa carpeta no es RoNavi: elige otra con `RONAVI_HOME` |
| "No se pudo preparar el entorno de RoNavi" | Borra `.venv/` y vuelve a ejecutar; pip necesita internet la primera vez |
| Caracteres raros o sin colores | Usa Windows Terminal (o cualquier terminal con color verdadero) y una fuente con bloques Unicode |
| Claude dice que el guardián lo bloqueó | Es lo esperado fuera del juego: haz ese cambio tú o desde RoNavi |
| El guardián no aparece en un juego clonado de otro PC | Proyectos → **Guardián** (o `ronavi sync-guards`): `settings.local.json` es propio de cada máquina |
