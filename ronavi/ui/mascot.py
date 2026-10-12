"""Navi, the RoNavi Studio fox with a red scarf.

Pixel art drawn with Unicode half blocks: each terminal cell shows two vertical
pixels ('▀' with a foreground colour for the top pixel and a background colour for
the bottom one). It stays sharp in any terminal font, costs a few hundred cells and
needs no images. Transparent pixels take the colour of whatever is behind.
"""

from __future__ import annotations

import random

from rich.style import Style
from rich.text import Text

PALETTE = {
    "O": "#ff8a3d",  # fur
    "D": "#c4561f",  # fur shade / outline
    "T": "#ffb37a",  # forehead highlight
    "W": "#fff3e3",  # cheeks and muzzle
    "P": "#ffc49b",  # inner ear
    "K": "#1b1622",  # eyes, nose, mouth
    "E": "#ffffff",  # eye shine
    "R": "#e5484d",  # scarf
    "r": "#9e2a35",  # scarf shade
    "L": "#ff8f93",  # scarf stripe
}

BIG = [
    "..D..................D..",
    "..DD................DD..",
    "..DPD..............DPD..",
    "..DPPD............DPPD..",
    "..DPPOD..........DOPPD..",
    "..DPPPODDDDDDDDDDOPPPD..",
    "..DPPOOOOOTTTTOOOOOPPD..",
    ".DOPOOOOOOTTTTOOOOOOPOD.",
    ".DOOOOOOOOOOOOOOOOOOOOD.",
    "DOOOOEKOOOOOOOOOOEKOOOOD",
    "DOOOOKKOOOOOOOOOOKKOOOOD",
    "DWOOOKKOOOOOOOOOOKKOOOWD",
    "DWWOOOOOOOOOOOOOOOOOOWWD",
    ".DWWWOOOOOOOOOOOOOOWWWD.",
    ".DWWWWWOOOOOOOOOOWWWWWD.",
    "..DWWWWWWOOOOOOWWWWWWD..",
    "...DWWWWWWWKKWWWWWWWD...",
    "....DWWWWWWKKWWWWWWD....",
    ".....DWWWWKWWKWWWWD.....",
    "...RRRDDWWWWWWWWDDRRR...",
    "..RRRRRRRRRRRRRRRRRRRR..",
    "..RLLRRRLLRRRLLRRRLLRR..",
    "..rRRRRRRRRRRRRRrRRRRr..",
    "...rrrrrrrrrrrrrRRRRr...",
    "..............RRLRR.....",
    ".............RRRLRr.....",
    ".............RRLRRr.....",
    ".............rLrLr......",
]

MINI = [
    ".D........D.",
    "DPD......DPD",
    "DOOOOTTOOOOD",
    "OOEKOOOOEKOO",
    "WOKKOOOOKKOW",
    "WWWOOKKOOWWW",
    ".WWWWWWWWWW.",
    "..DWWWWWWD..",
    ".RRRRRRRRRR.",
    ".rRLRRRLRRr.",
    "........RLR.",
    "........rRr.",
]

# Eye pixels per art: (row, col) of the 2x3 (big) or 2x2 (mini) eye blocks.
_BIG_EYES = [(r, c) for r in (9, 10, 11) for c in (5, 6, 17, 18)]
_MINI_EYES = [(r, c) for r in (3, 4) for c in (2, 3, 8, 9)]


def _with(grid: list[str], cells: dict[tuple[int, int], str]) -> list[str]:
    rows = [list(r) for r in grid]
    for (r, c), ch in cells.items():
        rows[r][c] = ch
    return ["".join(r) for r in rows]


def _blink(grid: list[str], eyes: list[tuple[int, int]], line_row: int, cols: set[int] | None = None) -> list[str]:
    cells = {}
    for r, c in eyes:
        if cols is not None and c not in cols:
            continue
        under = "O" if grid[r][c] in "EK" else grid[r][c]
        cells[(r, c)] = "K" if r == line_row else under
    return _with(grid, cells)


FRAMES = {
    "big": {
        "normal": BIG,
        "blink": _blink(BIG, _BIG_EYES, 10),
        "wink": _blink(BIG, _BIG_EYES, 10, cols={17, 18}),
    },
    "mini": {
        "normal": MINI,
        "blink": _blink(MINI, _MINI_EYES, 4),
        "wink": _blink(MINI, _MINI_EYES, 4, cols={8, 9}),
    },
}


def render(grid: list[str]) -> Text:
    """Pixel grid -> Rich Text, two pixel rows per text line."""
    rows = list(grid)
    if len(rows) % 2:
        rows.append("." * len(rows[0]))
    text = Text(no_wrap=True, overflow="crop")
    for i in range(0, len(rows), 2):
        top, bottom = rows[i], rows[i + 1]
        for t, b in zip(top, bottom):
            tc, bc = PALETTE.get(t), PALETTE.get(b)
            if tc and bc:
                text.append("▀", Style(color=tc, bgcolor=bc))
            elif tc:
                text.append("▀", Style(color=tc))
            elif bc:
                text.append("▄", Style(color=bc))
            else:
                text.append(" ")
        if i + 2 < len(rows):
            text.append("\n")
    return text


def fox(size: str = "big", mood: str = "normal") -> Text:
    return render(FRAMES[size].get(mood, FRAMES[size]["normal"]))


GREETINGS = [
    "¡Hola! Soy Navi. ¿Qué construimos hoy?",
    "La bufanda está lista. ¿Y tu próximo juego?",
    "Cada juego en su madriguera: nada se mezcla.",
    "¿Seguimos donde lo dejamos?",
    "Olfateo un hit en tu próxima idea.",
]

TIPS = [
    "El disco es la única verdad: el código llega a Studio por Rojo.",
    "Un solo servidor MCP de Studio y una sola conexión de Rojo.",
    "Antes de gastar cupo, quota-guard estima y te pregunta.",
    "Cada sección de create-roblox-game termina con HANDOFF.md y \"approved\".",
    "Las claves viven en variables de entorno, nunca en archivos ni en el chat.",
    "check.py en verde antes de cada commit: rojo build, lune, selene y stylua.",
    "Enter en un proyecto abre Claude Code justo en su carpeta.",
]


def greeting() -> str:
    return random.choice(GREETINGS)


def tip() -> str:
    return random.choice(TIPS)
