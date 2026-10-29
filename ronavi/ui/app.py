"""RoNavi Studio application: shared state and the actions every screen uses."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from textual import work
from textual.app import App
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.message import Message
from textual.theme import Theme

from ronavi import APP_NAME, __version__
from ronavi.core import environment as envmod
from ronavi.core import updates
from ronavi.core.environment import EnvCheck
from ronavi.core.guard import GuardError
from ronavi.core.ideas import Idea, discover_ideas, idea_env, prepare_idea_launch
from ronavi.core.launcher import claude_command, claude_executable, open_window, prepare_game_launch, run_here
from ronavi.core.paths import Studio
from ronavi.core.projects import Game, discover, launch_env
from ronavi.ui.modals import ConfirmScreen, Job, TaskScreen

RONAVI_THEME = Theme(
    name="ronavi",
    primary="#ff8a3d",
    secondary="#e5484d",
    accent="#ffb37a",
    foreground="#ece6f0",
    background="#141218",
    surface="#1c1922",
    panel="#27222f",
    success="#5ed6a0",
    warning="#ffcc66",
    error="#ff5d6c",
    dark=True,
    variables={
        "footer-key-foreground": "#ff8a3d",
        "block-cursor-background": "#ff8a3d",
        "block-cursor-foreground": "#141218",
        "input-selection-background": "#ff8a3d 35%",
    },
)


class EnvChanged(Message):
    """The doctor finished: every screen that shows status refreshes."""


class GamesChanged(Message):
    """A game was created, adopted or changed."""


class RoNaviApp(App[None]):
    TITLE = APP_NAME
    SUB_TITLE = f"v{__version__}"
    CSS_PATH = "styles.tcss"
    BINDINGS = [Binding("ctrl+q", "quit", "Salir", priority=True)]

    def __init__(self, studio: Studio | None = None, *, skip_welcome: bool = False, run_checks: bool = True):
        super().__init__()
        self.studio = studio or Studio.load()
        self.skip_welcome = skip_welcome
        self.run_checks = run_checks
        self.checks: list[EnvCheck] = []
        self.checks_loading = False
        self.games: list[Game] = []
        self.ideas: list[Idea] = []

    # ------------------------------------------------------------------ lifecycle

    def on_mount(self) -> None:
        self.register_theme(RONAVI_THEME)
        self.theme = "ronavi"
        self.reload_games()
        from ronavi.ui.main import MainScreen
        from ronavi.ui.welcome import WelcomeScreen

        self.push_screen(MainScreen())
        if self.studio.is_first_run:
            from ronavi.ui.wizard import WizardScreen
            self.push_screen(WizardScreen())
        if not self.skip_welcome:
            self.push_screen(WelcomeScreen())
        if self.run_checks:
            self.call_after_refresh(self.refresh_env)
            self._check_update()

    # ------------------------------------------------------------------ state

    def reload_games(self) -> None:
        self.games = discover(self.studio)
        self.ideas = discover_ideas(self.studio)
        self._broadcast(GamesChanged())

    def _broadcast(self, message: Message) -> None:
        """Tell every mounted screen and section that state changed. One bad widget never stops the rest."""
        for screen in list(self.screen_stack):
            for widget in [screen, *screen.walk_children()]:
                if not hasattr(widget, "ronavi_refresh") or not widget.is_mounted:
                    continue
                try:
                    widget.ronavi_refresh(message)
                except NoMatches:  # still composing: it refreshes itself on mount
                    pass

    def refresh_env(self) -> None:
        if not self.run_checks:  # tests: no doctor, no subprocesses
            return
        if not self.checks_loading:
            self.checks_loading = True
            self._broadcast(EnvChanged())
            self._load_checks()

    @work(thread=True, exclusive=True, group="doctor")
    def _load_checks(self) -> None:
        try:
            checks = envmod.run_doctor(self.studio)
        except Exception as exc:
            checks = [EnvCheck("RoNavi", "doctor.py", envmod.FAIL, f"no se pudo ejecutar: {exc}",
                               "python scripts/doctor.py", True)]
        self.call_from_thread(self._set_checks, checks)

    @work(thread=True, exclusive=True, group="update")
    def _check_update(self) -> None:
        """At most once a day; offline or slow just means no notice."""
        try:
            newer = updates.check_for_update(self.studio)
        except Exception:
            return
        if newer:
            self.call_from_thread(self.notify, f"Hay una versión nueva: RoNavi {newer}. "
                                  "Configuración → Actualizar RoNavi.", title="Actualización", timeout=12)

    def _set_checks(self, checks: list[EnvCheck]) -> None:
        self.checks = checks
        self.checks_loading = False
        self._broadcast(EnvChanged())

    def save_config(self) -> None:
        self.studio.save()

    # ------------------------------------------------------------------ running things

    def confirm(self, title: str, body: str, on_yes: Callable[[], None], *, yes: str = "Sí, continuar",
                danger: bool = False) -> None:
        def done(answer: bool | None) -> None:
            if answer:
                on_yes()
        self.push_screen(ConfirmScreen(title, body, yes, danger), done)

    def run_task(self, title: str, jobs: list[Job], after: Callable[[bool], None] | None = None) -> None:
        def done(ok: bool | None) -> None:
            self.reload_games()
            self.refresh_env()
            if after:
                after(bool(ok))
        self.push_screen(TaskScreen(title, jobs), done)

    def run_interactive(self, cmd: list[str], cwd: Path, *, env: dict[str, str] | None = None,
                        title: str = "", pause: bool = True) -> int:
        """Hand the terminal to `cmd` (installers, logins, Claude Code) and come back afterwards."""
        with self.suspend():
            print(f"\n\033[38;2;255;138;61m▌ RoNavi Studio\033[0m · {title or ' '.join(cmd[:2])}")
            print(f"\033[2m  carpeta: {cwd}\033[0m\n")
            code = run_here(cmd, cwd, env)
            if pause:
                try:
                    input(f"\n[código {code}] Pulsa Enter para volver a RoNavi Studio… ")
                except EOFError:
                    pass
        self.refresh()
        return code

    def claude_cmd(self, prompt: str | None = None) -> list[str] | None:
        try:
            return claude_command(self.studio, prompt)
        except GuardError as exc:
            self.notify(str(exc), severity="error", timeout=8)
            return None

    def open_game(self, game: Game, *, prompt: str | None = None, mode: str | None = None) -> None:
        """Open Claude Code in `game` after re-checking its guard and its git isolation."""
        try:
            prepare_game_launch(self.studio, game)
        except (GuardError, OSError) as exc:
            self.notify(str(exc), title="No se abrió Claude Code", severity="error", timeout=10)
            return
        cmd = self.claude_cmd(prompt)
        if not cmd:
            return
        env = launch_env(self.studio, game)
        self.studio.config.last_game = game.slug
        self.save_config()
        mode = mode or self.studio.config.launch_mode
        if mode == "window":
            try:
                open_window(cmd, game.root, f"RoNavi · {game.name}", env)
                self.notify(f"Claude Code se abrió en otra ventana, en {game.slug}.", title="Listo")
            except (GuardError, OSError) as exc:
                self.notify(str(exc), severity="error")
        else:
            self.run_interactive(cmd, game.root, env=env, title=f"Claude Code en {game.name}", pause=False)
            self.reload_games()

    def open_idea(self, idea: Idea, *, prompt: str | None = None, mode: str | None = None) -> None:
        """Open Claude Code in an idea folder (research only), after refreshing its guard."""
        try:
            prepare_idea_launch(self.studio, idea)
        except (GuardError, OSError) as exc:
            self.notify(str(exc), title="No se abrió Claude Code", severity="error", timeout=10)
            return
        cmd = self.claude_cmd(prompt)
        if not cmd:
            return
        env = idea_env(self.studio, idea)
        mode = mode or self.studio.config.launch_mode
        if mode == "window":
            try:
                open_window(cmd, idea.root, f"RoNavi · idea {idea.id}", env)
                self.notify(f"Claude Code se abrió en otra ventana, en la idea {idea.id}.", title="Listo")
            except (GuardError, OSError) as exc:
                self.notify(str(exc), severity="error")
        else:
            self.run_interactive(cmd, idea.root, env=env, title=f"Claude Code en la idea {idea.id}", pause=False)
            self.reload_games()

    def open_claude_in_studio(self, prompt: str | None, title: str) -> None:
        """Claude Code at the studio root, for studio-level chores (/mcp, /roblox-skills-setup)."""
        exe = claude_executable()
        if not exe:
            self.notify("Claude Code no está instalado (Herramientas → Instalar programas).", severity="error")
            return
        cmd = [exe] + ([prompt] if prompt else [])
        self.run_interactive(cmd, self.studio.root, title=title, pause=False)
        self.refresh_env()

    def game_tool(self, game: Game, cmd: list[str], title: str, *, window: bool = False) -> None:
        env = launch_env(self.studio, game)
        if window:
            try:
                open_window(cmd, game.root, title, env)
                self.notify(f"{title}: abierto en otra ventana.")
            except (GuardError, OSError) as exc:
                self.notify(str(exc), severity="error")
            return
        self.run_task(title, [Job(title, cmd=cmd, cwd=game.root, env=env)])

    def env_python(self) -> str:
        return envmod.system_python()


def run_tui(studio: Studio | None = None) -> int:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    RoNaviApp(studio).run()
    return 0
