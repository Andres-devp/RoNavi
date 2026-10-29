"""First-run wizard: detect what is missing, install it, check again."""

from __future__ import annotations

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Label, ListItem, ListView, Static

from ronavi.core import environment as envmod
from ronavi.core import integrations
from ronavi.core.environment import SetupStep
from ronavi.core.launcher import claude_executable
from ronavi.ui.modals import Job
from ronavi.ui.welcome import Fox

ICONS = {True: ("✔", "#5ed6a0"), False: ("✘", "#ff5d6c"), None: ("?", "#ffcc66")}


class WizardScreen(Screen[None]):
    BINDINGS = [
        Binding("m", "mark_done", "Marcar hecho"),
        Binding("r", "recheck", "Comprobar"),
        Binding("escape", "finish", "Terminar"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.steps: list[SetupStep] = []
        self.status: dict[str, bool | None] = {}
        self.checking = True

    def compose(self) -> ComposeResult:
        with Horizontal(id="wizard"):
            with Vertical(id="wiz-side"):
                yield Fox("big", animate=self.app.studio.config.animations, id="wiz-fox")  # type: ignore[attr-defined]
                yield Static("", id="wiz-speech", classes="speech")
            with Vertical(id="wiz-main"):
                yield Label("Asistente de instalación", classes="section-title")
                yield Static("RoNavi detecta lo que falta, lo instala con los scripts del estudio y vuelve a "
                             "comprobar. Lo que ya está bien no se repite.", classes="muted")
                yield ListView(id="wiz-steps")
                with VerticalScroll(id="wiz-detail-box"):
                    yield Static("", id="wiz-detail")
                yield Checkbox("Incluir programas opcionales (Node, ffmpeg, PowerShell 7, shellcheck, GitHub CLI)",
                               id="wiz-optional")
                with Horizontal(classes="button-row"):
                    yield Button("Ejecutar paso", id="wiz-run", variant="primary")
                    yield Button("Marcar como hecho", id="wiz-mark")
                    yield Button("Comprobar de nuevo", id="wiz-check")
                    yield Button("Terminar", id="wiz-finish", variant="success")
        yield Footer()

    async def on_mount(self) -> None:
        await self.build_steps()
        self.ronavi_refresh(None)

    async def build_steps(self) -> None:
        """(Re)build the step list. clear() and extend() are awaited: removal is asynchronous."""
        optional = self.query_one("#wiz-optional", Checkbox).value
        lv = self.query_one("#wiz-steps", ListView)
        index = lv.index or 0
        self.steps = envmod.setup_steps(self.app.studio, optional)  # type: ignore[attr-defined]
        await lv.clear()
        await lv.extend(ListItem(Label(self._line(step))) for step in self.steps)
        lv.index = min(index, len(self.steps) - 1)
        self.show_detail()

    def _line(self, step: SetupStep) -> Text:
        icon, color = ICONS[self.status.get(step.key)] if not self.checking else ("…", "#8b8597")
        kind = {"interactive": "en la terminal", "stream": "automático", "manual": "manual",
                "action": "un clic"}[step.kind]
        return Text.assemble((f" {icon} ", f"bold {color}"), (step.title, "bold"), (f"   {kind}", "dim italic"))

    def ronavi_refresh(self, _message: object) -> None:
        if getattr(self.app, "checks_loading", False):
            self.checking = True
            self._repaint()
            self.query_one("#wiz-speech", Static).update("« Olfateando tu PC… dame un momento. »")
            return
        self._compute_status()

    @work(thread=True, exclusive=True, group="wizard")
    def _compute_status(self) -> None:
        app = self.app
        status = {s.key: envmod.step_done(s, app.studio, app.checks) for s in self.steps}  # type: ignore[attr-defined]
        app.call_from_thread(self._apply_status, status)

    def _apply_status(self, status: dict[str, bool | None]) -> None:
        self.status, self.checking = status, False
        self._repaint()
        pending = [s for s in self.steps if status.get(s.key) is False]
        speech = self.query_one("#wiz-speech", Static)
        fox = self.query_one("#wiz-fox", Fox)
        if not pending:
            speech.update("« ¡Todo listo! Pulsa Terminar y creamos tu primer juego. »")
            fox.mood("wink")
        else:
            speech.update(f"« Faltan {len(pending)} paso{'s' if len(pending) != 1 else ''}. "
                          f"Empecemos por: {pending[0].title}. »")
            lv = self.query_one("#wiz-steps", ListView)
            lv.index = self.steps.index(pending[0])
        self.show_detail()

    def _repaint(self) -> None:
        lv = self.query_one("#wiz-steps", ListView)
        for item, step in zip(lv.children, self.steps):
            item.query_one(Label).update(self._line(step))

    def current(self) -> SetupStep | None:
        lv = self.query_one("#wiz-steps", ListView)
        if lv.index is None or not 0 <= lv.index < len(self.steps):
            return None
        return self.steps[lv.index]

    def on_list_view_highlighted(self, _: ListView.Highlighted) -> None:
        self.show_detail()

    async def on_checkbox_changed(self, _: Checkbox.Changed) -> None:
        await self.build_steps()

    def show_detail(self) -> None:
        step = self.current()
        detail = self.query_one("#wiz-detail", Static)
        if not step:
            detail.update("")
            return
        state = self.status.get(step.key)
        text = Text()
        text.append(step.title + "\n", style="bold #ff8a3d")
        text.append(step.why + "\n")
        if step.manual:
            text.append("\n")
            for line in step.manual:
                text.append("  • " + line + "\n")
        if step.commands:
            text.append("\nComandos:\n", style="#8b8597")
            for cmd in step.commands:
                text.append("  $ " + " ".join(cmd[-4:] if len(cmd) > 6 else cmd) + "\n", style="#8b8597")
        text.append("\nEstado: ", style="bold")
        text.append({True: "hecho", False: "pendiente", None: "no se puede comprobar solo"}[state]
                    if not self.checking else "comprobando…")
        detail.update(text)
        self.query_one("#wiz-mark", Button).disabled = step.kind != "manual"
        self.query_one("#wiz-run", Button).disabled = step.kind == "manual"

    # ------------------------------------------------------------------ actions

    def on_button_pressed(self, event: Button.Pressed) -> None:
        {"wiz-run": self.action_run_step, "wiz-mark": self.action_mark_done,
         "wiz-check": self.action_recheck, "wiz-finish": self.action_finish}[event.button.id or ""]()

    def on_list_view_selected(self, _: ListView.Selected) -> None:
        self.action_run_step()

    def action_recheck(self) -> None:
        self.app.refresh_env()  # type: ignore[attr-defined]

    def action_mark_done(self) -> None:
        step = self.current()
        if not step or step.kind != "manual":
            return
        cfg = self.app.studio.config  # type: ignore[attr-defined]
        if step.key not in cfg.manual_done:
            cfg.manual_done.append(step.key)
        self.app.save_config()  # type: ignore[attr-defined]
        self._compute_status()

    def action_run_step(self) -> None:
        step = self.current()
        app = self.app
        if not step or step.kind == "manual":
            return
        studio = app.studio  # type: ignore[attr-defined]
        if step.kind == "interactive":
            cmds = [[claude_executable() or "claude", *c[1:]] if c[0] == "claude" else c for c in step.commands]
            note = ("Se suspende RoNavi y el paso corre en esta terminal; al terminar vuelves aquí."
                    if step.key != "login" else
                    "Se abre Claude Code. Inicia sesión y escribe /exit para volver a RoNavi.")

            def go() -> None:
                for cmd in cmds:
                    app.run_interactive(cmd, studio.root, title=step.title)  # type: ignore[attr-defined]
                app.refresh_env()  # type: ignore[attr-defined]
            app.confirm(step.title, f"{step.why}\n\n{note}", go)  # type: ignore[attr-defined]
        elif step.kind == "stream":
            jobs = [Job(" ".join(c[-2:]) if "skills_sync" in " ".join(c) else step.title, cmd=c, cwd=studio.root)
                    for c in step.commands]
            app.confirm(step.title, step.why, lambda: app.run_task(step.title, jobs))  # type: ignore[attr-defined]
        elif step.key == "gameshome":
            if not integrations.can_set_env():
                app.notify(f"En tu ~/.zshrc o ~/.bashrc: export ROBLOX_GAMES_HOME=\"{studio.games_home}\"",
                           timeout=15)
                return

            def set_home() -> None:
                integrations.set_user_env("ROBLOX_GAMES_HOME", str(studio.games_home))
                app.notify(f"ROBLOX_GAMES_HOME = {studio.games_home}", title="Hecho")
                self._compute_status()
            app.confirm("Carpeta de juegos", f"Se definirá ROBLOX_GAMES_HOME = {studio.games_home} "
                        "para tu usuario (las terminales nuevas la verán).", set_home)  # type: ignore[attr-defined]
        elif step.key == "path":
            def add_path() -> None:
                app.notify(integrations.add_to_user_path(studio.root), title="PATH")  # type: ignore[attr-defined]
                self._compute_status()
            app.confirm(step.title, f"{step.why}\n\nAbre una terminal nueva y escribe ronavi.",  # type: ignore[attr-defined]
                        add_path)

    def action_finish(self) -> None:
        app = self.app
        pending = [s.title for s in self.steps if self.status.get(s.key) is False]

        def close() -> None:
            app.studio.config.setup_done = True  # type: ignore[attr-defined]
            app.save_config()  # type: ignore[attr-defined]
            self.dismiss()
        if pending and not self.checking:
            app.confirm("Quedan pasos pendientes", "Pendiente: " + ", ".join(pending) +  # type: ignore[attr-defined]
                        ".\n\nPuedes volver al asistente cuando quieras desde Configuración.", close,
                        yes="Terminar igualmente")
        else:
            close()
