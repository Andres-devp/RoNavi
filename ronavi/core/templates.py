"""Text that RoNavi writes into a game. Spanish for people, English for identifiers."""

from __future__ import annotations

BLOCK_BEGIN = "<!-- ronavi:begin (gestionado por RoNavi Studio; se reescribe al sincronizar) -->"
BLOCK_END = "<!-- ronavi:end -->"

GENRES = [
    ("obby", "Obby (parkour)"),
    ("tycoon", "Tycoon"),
    ("simulator", "Simulator"),
    ("tower-defense", "Tower defense"),
    ("horror", "Horror"),
    ("roleplay", "Roleplay"),
    ("fighting", "Lucha / PvP"),
    ("racing", "Carreras"),
    ("puzzle", "Puzzle"),
    ("other", "Otro"),
]
GENRE_LABELS = dict(GENRES)

# Lines every game's .gitignore must have. RoNavi only appends the missing ones.
GITIGNORE_LINES = [
    "# Roblox build output and generated files",
    "*.rbxl",
    "*.rbxlx",
    "*.rbxl.lock",
    "*.rbxlx.lock",
    "Packages/",
    "ServerPackages/",
    "DevPackages/",
    "sourcemap.json",
    "",
    "# Machine-specific files (RoNavi Studio regenerates them)",
    ".claude/settings.local.json",
    ".claude/ronavi-guard.json",
    "LOCAL.md",
    ".env*",
    "",
    "# OS / editor noise",
    ".DS_Store",
    "Thumbs.db",
    "__pycache__/",
]


def claude_block(name: str, slug: str, genre: str, description: str) -> str:
    genre_label = GENRE_LABELS.get(genre, genre)
    desc = f"\n\n> {description}" if description else ""
    return f"""{BLOCK_BEGIN}
# {name}

Juego de Roblox ({genre_label}) creado con **RoNavi Studio**. **Respóndeme siempre en español.**
Documentación para humanos en español; código, nombres de archivo e identificadores en inglés.{desc}

## Tu ámbito: solo esta carpeta

- Este juego es un proyecto independiente con su propio git. **Todo lo que escribas va dentro de
  esta carpeta.** Nunca modifiques la plantilla del estudio ni otros juegos.
- RoNavi instaló un guardián (`.claude/hooks/ronavi_guard.py`) que bloquea escrituras fuera de este
  juego. Si te bloquea, no lo esquives: explica al usuario qué necesitas y que lo haga él desde RoNavi.
- Las skills del estudio están disponibles porque RoNavi abre Claude Code con `--add-dir` hacia el
  estudio. Puedes **leer** sus archivos (por ejemplo `docs/quotas.md`), no editarlos.
- `ROBLOX_GAMES_HOME` apunta a la carpeta que contiene este juego. Cuando una skill pida la carpeta del
  juego, es **esta** carpeta (`{slug}`): no crees otra.

## Etapas (`create-roblox-game`)

Una sección por sesión: investigación y plan → código → arte → animación y sonido → playtest →
publicar. Al cerrar cada sección escribe `HANDOFF.md` en esta carpeta y espera a que el usuario diga
"approved" antes de empezar la siguiente.

## Reglas de trabajo

1. **El disco es la única verdad.** El código se edita en disco y llega a Studio por Rojo. Nunca edites
   scripts dentro de Studio ni los sobrescribas por MCP: el MCP es para geometría, inspección y capturas.
2. **La lógica pura va en `src/shared/Core/`**, con su spec.
3. **La red pasa por un solo `Net.luau`.**
4. **Lo cosmético nunca rompe la jugabilidad**: efectos asíncronos, con `pcall`.
5. **Todo valor ajustable va en `src/shared/Config/`.**

Además: Script Sync de Studio apagado y una sola conexión de Rojo; un solo servidor MCP de Studio a la
vez; `get_studio_state` en cada cambio de etapa; los subagentes nunca escriben en Studio; todo lo que
escribe en Studio o gasta cupo pide permiso (usa `quota-guard` antes). Las claves viven solo en
variables de entorno: nunca pidas un valor en el chat.

## Comandos (dentro de esta carpeta)

```bash
rokit install
wally install
python ~/.claude/skills/roblox-code/scripts/check.py   # rojo build, lune, selene, stylua: en verde
rojo serve
```

Definición de terminado: `check.py` en verde, playtest descrito (incluida la marca de build en Output)
y commit pequeño con Conventional Commits en **el git de este juego**.
{BLOCK_END}
"""


def upsert_block(existing: str | None, block: str) -> str:
    """Replace RoNavi's managed block, or put it on top, keeping everything else untouched."""
    if not existing:
        return block
    start, end = existing.find(BLOCK_BEGIN), existing.find(BLOCK_END)
    if start != -1 and end > start:
        return existing[:start] + block.rstrip("\n") + existing[end + len(BLOCK_END):]
    return block + "\n" + existing


def readme(name: str, genre: str, description: str) -> str:
    genre_label = GENRE_LABELS.get(genre, genre)
    desc = f"{description}\n\n" if description else ""
    return f"""# {name}

{desc}Juego de Roblox ({genre_label}) creado con RoNavi Studio. Proyecto independiente con su propio git.

## Continuar

Abre **RoNavi Studio**, elige este juego en *Proyectos* y pulsa **Enter**: abre Claude Code aquí, con
las skills del estudio y el guardián de rutas ya configurados.

## Comandos

```bash
rokit install      # toolchain fijada (rojo, wally, lune, selene, stylua)
wally install      # paquetes -> Packages/
python ~/.claude/skills/roblox-code/scripts/check.py   # las 4 revisiones
rojo serve         # y conecta el plugin de Rojo en Studio (una sola vez)
```
"""


def first_prompt(name: str, slug: str, genre: str, description: str) -> str:
    """Initial prompt for a brand-new game. Only safe characters (it goes through a command line)."""
    genre_label = GENRE_LABELS.get(genre, genre).split(" (")[0].lower()
    about = f" Idea: {description}." if description else ""
    text = (f"complete the research and plan stage for a {genre_label} game called {name}.{about} "
            f"The current folder IS the game folder ({slug}): write everything here and do not create "
            f"another game folder.")
    return sanitize_prompt(text)


def sanitize_prompt(text: str) -> str:
    """Drop characters that a Windows command line could interpret (quotes, %, ^, &, |, <, >)."""
    return "".join(ch for ch in text if ch not in '"%^&|<>`$!\r\n').strip()
