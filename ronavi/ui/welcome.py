"""Welcome screen: Navi, the wordmark and a first look at the environment."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Static

from ronavi import __version__
from ronavi.core.environment import counts
from ronavi.ui import mascot

WORDMARK = [
    "█▀█ █▀█ █▄ █ ▄▀█ █ █ █",
    "█▀▄ █▄█ █ ▀█ █▀█ ▀▄▀ █",
]
GRADIENT = ["#ffb37a", "#ff9a52", "#ff8a3d", "#f8713f", "#ee5a45", "#e5484d"]


def wordmark() -> Text:
    text = Text(no_wrap=True)
    width = len(WORDMARK[0])
    for i, row in enumerate(WORDMARK):
        for x, ch in enumerate(row):
            text.append(ch, style=f"bold {GRADIENT[min(len(GRADIENT) - 1, x * len(GRADIENT) // width)]}")
        if i + 1 < len(WORDMARK):
            text.append("\n")
    text.append("\nS  T  U  D  I  O", style="bold #ece6f0")
    return text


class Fox(Static):
    """Navi with an occasional blink. Animation can be turned off in Configuración."""

    def __init__(self, size: str = "big", animate: bool = True, **kwargs):
        super().__init__(mascot.fox(size), **kwargs)
        self.size_name, self.animate, self._tick = size, animate, 0

    def on_mount(self) -> None:
        if self.animate:
            self.set_interval(0.35, self._step)

    def _step(self) -> None:
        self._tick = (self._tick + 1) % 14
        mood = "blink" if self._tick == 0 else "normal"
        if self._tick in (0, 1):
            self.update(mascot.fox(self.size_name, mood))

    def mood(self, mood: str) -> None:
        self.update(mascot.fox(self.size_name, mood))


class WelcomeScreen(Screen[None]):
    BINDINGS = [Binding("enter,space,escape", "start", "Empezar")]

    def compose(self) -> ComposeResult:
        app = self.app
        with Center(id="welcome"):
            with Horizontal(id="welcome-row"):
                yield Fox("big", animate=app.studio.config.animations, id="welcome-fox")  # type: ignore[attr-defined]
                with Vertical(id="welcome-text"):
                    yield Static(wordmark(), id="wordmark")
                    yield Static("Crea y administra juegos de Roblox con IA, desde tu terminal.", classes="tagline")
                    yield Static(f"« {mascot.greeting()} »", classes="speech")
                    yield Static("Comprobando tu entorno…", id="welcome-status", classes="muted")
                    yield Static(f"Consejo: {mascot.tip()}", classes="tip")
                    yield Static(Text.assemble(("Enter", "bold #ff8a3d"), " para empezar  ·  ",
                                               ("Ctrl+Q", "bold #ff8a3d"), " para salir"), classes="hint")
            yield Static(f"v{__version__} · {app.studio.root}", id="welcome-foot", classes="muted")  # type: ignore[attr-defined]

    def on_mount(self) -> None:
        self.ronavi_refresh(None)

    def ronavi_refresh(self, _message: object) -> None:
        app = self.app
        status = self.query_one("#welcome-status", Static)
        if getattr(app, "checks_loading", False) or not getattr(app, "checks", None):
            status.update("Comprobando tu entorno…")
            return
        ok, warn, fail = counts(app.checks)  # type: ignore[attr-defined]
        games = len(getattr(app, "games", []))
        line = Text.assemble(("● ", "#5ed6a0" if not fail else "#ff5d6c"),
                             f"Entorno: {ok} bien · {warn} avisos · {fail} por resolver   ",
                             ("● ", "#ffb37a"), f"{games} juego{'s' if games != 1 else ''}")
        status.update(line)
        if fail == 0:
            self.query_one("#welcome-fox", Fox).mood("wink")

    def action_start(self) -> None:
        self.dismiss()
