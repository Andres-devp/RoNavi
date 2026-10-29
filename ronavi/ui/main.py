"""Main screen: sidebar navigation and the eight sections."""

from __future__ import annotations

import time
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (Button, Checkbox, ContentSwitcher, DataTable, Footer, Input, Label, OptionList,
                             RadioButton, RadioSet, Select, Static, Switch)
from textual.widgets.option_list import Option

from ronavi import __version__
from ronavi.core import environment as envmod
from ronavi.core import integrations, skills, updates
from ronavi.core import templates as T
from ronavi.core.guard import GuardError, is_within, same_path, validate_name
from ronavi.core.ideas import Idea, create_idea
from ronavi.core.launcher import claude_executable, open_folder, open_vscode
from ronavi.core.projects import (Game, adopt_game, create_game, launch_env, scaffold_script, scope_for,
                                  sync_all_guards, sync_guard)
from ronavi.ui import mascot
from ronavi.ui.modals import Job, SecretScreen, TextScreen
from ronavi.ui.welcome import Fox

SECTIONS = [
    ("home", "◆ Inicio"),
    ("projects", "▤ Proyectos"),
    ("ideas", "✦ Ideas"),
    ("new", "✚ Nuevo juego"),
    ("skills", "✧ Skills"),
    ("tools", "▲ Herramientas"),
    ("integrations", "⇄ Integraciones"),
    ("settings", "≡ Configuración"),
]
STATUS_ICON = {envmod.OK: ("✔", "#5ed6a0"), envmod.WARN: ("!", "#ffcc66"), envmod.FAIL: ("✘", "#ff5d6c")}


def ago(ts: float) -> str:
    if not ts:
        return "—"
    s = int(time.time() - ts)
    for unit, n in (("d", 86400), ("h", 3600), ("min", 60)):
        if s >= n:
            return f"hace {s // n} {unit}"
    return "ahora"


class Section(VerticalScroll):
    """Base for sections: access to the app and a refresh hook."""

    @property
    def rapp(self):  # the RoNaviApp, typed loosely to keep Textual's generics out of the way
        return self.app

    def ronavi_refresh(self, _message: object) -> None:
        pass


# ============================================================================ home

def last_game(app) -> Game | None:
    """The game to continue: the last one opened, else the most recently touched managed game."""
    managed = sorted((g for g in app.games if g.managed), key=lambda g: g.modified, reverse=True)
    return next((g for g in managed if g.slug == app.studio.config.last_game), managed[0] if managed else None)


class HomeSection(Section):
    def compose(self) -> ComposeResult:
        with Horizontal(id="home-hero"):
            yield Fox("big", animate=self.rapp.studio.config.animations, id="home-fox")
            with Vertical(id="home-hero-text"):
                yield Label("¡Hola! Soy Navi.", classes="hero-title")
                yield Static(f"« {mascot.greeting()} »", classes="speech")
                yield Static("", id="home-env", classes="card")
                with Horizontal(classes="button-row"):
                    yield Button("▶ Continuar", id="home-continue", variant="primary")
                    yield Button("✚ Nuevo juego", id="home-new")
                    yield Button("✦ Explorar idea", id="home-idea")
                    yield Button("Asistente", id="home-wizard")
                    yield Button("Diagnóstico", id="home-doctor")
        yield Label("Juegos recientes", classes="subtitle")
        yield Static("", id="home-recent", classes="card")
        yield Static(f"Consejo: {mascot.tip()}", classes="tip")

    def on_mount(self) -> None:
        self.ronavi_refresh(None)

    def ronavi_refresh(self, _message: object) -> None:
        app = self.rapp
        env = self.query_one("#home-env", Static)
        if app.checks_loading or not app.checks:
            env.update(Text("● Comprobando tu entorno…", style="#8b8597"))
        else:
            ok, warn, fail = envmod.counts(app.checks)
            t = Text()
            t.append("● ", style="#5ed6a0" if not fail else "#ff5d6c")
            t.append("Entorno listo" if not fail else f"{fail} cosa{'s' if fail != 1 else ''} por resolver",
                     style="bold")
            t.append(f"   {ok} bien · {warn} avisos · {fail} errores\n", style="#8b8597")
            for c in [c for c in app.checks if c.status == envmod.FAIL][:4]:
                t.append(f"  ✘ {c.name}: ", style="#ff5d6c")
                t.append(f"{c.fix or c.detail}\n", style="#ece6f0")
            if fail:
                t.append("  → Herramientas o el Asistente lo arreglan.", style="#ffb37a")
            env.update(t)
        games = sorted(app.games, key=lambda g: g.modified, reverse=True)
        recent = Text()
        if not games:
            recent.append("Aún no hay juegos. Pulsa ", style="#8b8597")
            recent.append("✚ Nuevo juego", style="bold #ff8a3d")
            recent.append(" para crear el primero.", style="#8b8597")
        for g in games[:5]:
            mark = "★ " if g.slug == app.studio.config.last_game else "  "
            recent.append(mark, style="#ffb37a")
            recent.append(f"{g.name:<24}", style="bold")
            recent.append(f" {T.GENRE_LABELS.get(g.genre, g.genre):<16} {g.stage:<8} {ago(g.modified)}\n",
                          style="#8b8597")
        self.query_one("#home-recent", Static).update(recent)
        last = last_game(app)
        cont = self.query_one("#home-continue", Button)
        cont.label = f"▶ Continuar {last.name}" if last else "▶ Continuar"
        cont.disabled = last is None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        screen = self.screen
        bid = event.button.id
        if bid == "home-continue":
            if last := last_game(self.rapp):
                self.rapp.open_game(last)
        elif bid == "home-new":
            screen.show_section("new")
        elif bid == "home-idea":
            screen.show_section("ideas")
        elif bid == "home-wizard":
            from ronavi.ui.wizard import WizardScreen
            self.app.push_screen(WizardScreen())
        elif bid == "home-doctor":
            screen.show_section("tools")
            self.rapp.refresh_env()


# ============================================================================ projects

class ProjectsSection(Section):
    BINDINGS = [
        Binding("w", "open_window", "Ventana nueva"),
        Binding("f", "folder", "Carpeta"),
        Binding("v", "vscode", "VS Code"),
        Binding("g", "guard", "Guardián"),
        Binding("a", "adopt", "Adoptar"),
        Binding("c", "check", "check.py"),
    ]

    def compose(self) -> ComposeResult:
        yield Label("Proyectos", classes="section-title")
        yield Static("", id="pj-home", classes="muted")
        with Horizontal(id="pj-body"):
            yield DataTable(id="pj-table", cursor_type="row", zebra_stripes=True)
            with Vertical(id="pj-side", classes="card"):
                yield Static("", id="pj-detail")
        with Horizontal(classes="button-row"):
            yield Button("▶ Abrir Claude Code", id="pj-open", variant="primary")
            yield Button("Ventana nueva", id="pj-window")
            yield Button("Carpeta", id="pj-folder")
            yield Button("VS Code", id="pj-code")
            yield Button("Adoptar", id="pj-adopt")
            yield Button("Guardián", id="pj-guard")
        with Horizontal(classes="button-row"):
            yield Button("rokit install", id="pj-rokit", classes="small")
            yield Button("wally install", id="pj-wally", classes="small")
            yield Button("check.py", id="pj-check", classes="small")
            yield Button("rojo serve", id="pj-serve", classes="small")
            yield Button("Recargar", id="pj-reload", classes="small")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.git: dict[str, str] = {}

    def on_mount(self) -> None:
        table = self.query_one("#pj-table", DataTable)
        table.add_column("Juego")
        table.add_column("Género")
        table.add_column("Etapa")
        table.add_column("Git", width=12)
        table.add_column("Guardián", width=14)
        table.add_column("Modificado")
        self.ronavi_refresh(None)

    def ronavi_refresh(self, message: object) -> None:
        from ronavi.ui.app import EnvChanged
        if isinstance(message, EnvChanged):
            return
        app = self.rapp
        self.query_one("#pj-home", Static).update(f"Carpeta de juegos: {app.studio.games_home}")
        table = self.query_one("#pj-table", DataTable)
        current = self.selected()
        table.clear()
        for g in app.games:
            guard = Text("✔ activo", style="#5ed6a0") if g.guard_installed else (
                Text("✘ falta", style="#ff5d6c") if g.managed else Text("sin gestionar", style="#ffcc66"))
            table.add_row(Text(g.name, style="bold"), T.GENRE_LABELS.get(g.genre, g.genre) if g.managed else "—",
                          g.stage, self.git.get(g.slug, "…"), guard, ago(g.modified), key=g.slug)
        if current:
            try:
                table.move_cursor(row=table.get_row_index(current.slug))
            except Exception:
                pass
        self.show_detail()
        self._load_git()

    @work(thread=True, exclusive=True, group="git")
    def _load_git(self) -> None:
        result = {}
        for g in list(self.rapp.games):
            try:
                result[g.slug] = g.git_summary()
            except Exception:
                result[g.slug] = "?"
        self.app.call_from_thread(self._apply_git, result)

    def _apply_git(self, result: dict[str, str]) -> None:
        self.git = result
        table = self.query_one("#pj-table", DataTable)
        for slug, summary in result.items():
            try:
                table.update_cell(slug, list(table.columns)[3], summary)
            except Exception:
                pass
        self.show_detail()

    def selected(self) -> Game | None:
        table = self.query_one("#pj-table", DataTable)
        if not table.row_count:
            return None
        try:
            key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        except Exception:
            return None
        return next((g for g in self.rapp.games if g.slug == key), None)

    def show_detail(self) -> None:
        g = self.selected()
        detail = self.query_one("#pj-detail", Static)
        if not g:
            detail.update(Text("No hay juegos todavía.\n\nCrea uno en ✚ Nuevo juego.", style="#8b8597"))
            return
        t = Text()
        t.append(g.name + "\n", style="bold #ff8a3d")
        if g.description:
            t.append(g.description + "\n", style="italic")
        t.append(f"\n{g.root}\n", style="#8b8597")
        t.append(f"\nGestionado: {'sí' if g.managed else 'no (pulsa Adoptar)'}\n")
        t.append(f"Git: {self.git.get(g.slug, '…')}\n")
        t.append(f"Código Rojo: {'sí' if g.has_code else 'todavía no'}\n")
        t.append(f"HANDOFF.md: {'sí' if g.has_handoff else 'no'}\n")
        t.append(f"Guardián: {'activo' if g.guard_installed else 'falta'}\n")
        if g.created:
            t.append(f"Creado: {g.created[:10]}\n", style="#8b8597")
        t.append("\nEnter abre Claude Code aquí, con las skills del estudio y escrituras limitadas a esta carpeta.",
                 style="#8b8597")
        detail.update(t)
        self.query_one("#pj-adopt", Button).disabled = g.managed

    @on(DataTable.RowHighlighted)
    def _highlighted(self, _: DataTable.RowHighlighted) -> None:
        self.show_detail()

    @on(DataTable.RowSelected)
    def _selected(self, _: DataTable.RowSelected) -> None:
        self.action_open()

    def _need(self, managed: bool = True) -> Game | None:
        g = self.selected()
        if not g:
            self.app.notify("Elige un juego primero.", severity="warning")
            return None
        if managed and not g.managed:
            self.app.notify(f"{g.name} no está gestionado: pulsa Adoptar.", severity="warning")
            return None
        return g

    def action_open(self) -> None:
        if g := self._need():
            self.rapp.open_game(g)

    def action_open_window(self) -> None:
        if g := self._need():
            self.rapp.open_game(g, mode="window")

    def action_folder(self) -> None:
        if g := self._need(managed=False):
            open_folder(g.root)

    def action_vscode(self) -> None:
        if g := self._need(managed=False):
            try:
                open_vscode(g.root)
            except GuardError as exc:
                self.app.notify(str(exc), severity="error")

    def action_guard(self) -> None:
        if g := self._need():
            app = self.rapp
            app.run_task(f"Guardián de {g.name}", [Job("Reinstalar guardián y reglas de permisos",
                                                           func=lambda log: sync_guard(app.studio, g, log))])

    def action_adopt(self) -> None:
        g = self._need(managed=False)
        if not g or g.managed:
            return
        app = self.rapp
        app.confirm(f"Adoptar {g.name}",
                    f"RoNavi añadirá a {g.root}:\n• .ronavi/project.json, CLAUDE.md (bloque gestionado), README si "
                    "falta\n• .claude/settings.json, .mcp.json, guardián y .gitignore\n• git init si no tiene git\n\n"
                    "No borra ni sobrescribe nada tuyo.",
                    lambda: app.run_task(f"Adoptar {g.name}", [Job("Adoptar", func=lambda log: adopt_game(
                        app.studio, g, progress=log))]))

    def action_check(self) -> None:
        if g := self._need():
            script = Path.home() / ".claude" / "skills" / "roblox-code" / "scripts" / "check.py"
            if not script.exists():
                self.app.notify("check.py no existe: instala las skills (Skills → Instalar).", severity="error")
                return
            self.rapp.game_tool(g, [envmod.system_python(), str(script)], f"check.py en {g.name}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        simple = {"pj-open": self.action_open, "pj-window": self.action_open_window, "pj-folder": self.action_folder,
                  "pj-code": self.action_vscode, "pj-adopt": self.action_adopt, "pj-guard": self.action_guard,
                  "pj-check": self.action_check, "pj-reload": self.rapp.reload_games}
        if bid in simple:
            simple[bid]()
            return
        g = self._need()
        if not g:
            return
        if bid == "pj-rokit":
            # Interactive on purpose: Rokit asks whether you trust each tool the first time.
            self.rapp.run_interactive(["rokit", "install"], g.root, env=launch_env(self.rapp.studio, g),
                                      title=f"rokit install en {g.name}")
        elif bid == "pj-wally":
            self.rapp.game_tool(g, ["wally", "install"], f"wally install en {g.name}")
        elif bid == "pj-serve":
            self.rapp.game_tool(g, ["rojo", "serve"], f"rojo serve · {g.name}", window=True)


# ============================================================================ ideas

class IdeasSection(Section):
    BINDINGS = [Binding("f", "folder", "Carpeta")]

    def compose(self) -> ComposeResult:
        yield Label("Ideas", classes="section-title")
        yield Static("¿Aún no sabes qué juego hacer? Claude investiga el mercado y te propone tres conceptos en "
                     "una carpeta de ideas (work/ideas/), sin nombre, género ni git. Cuando elijas uno, conviértelo "
                     "en juego: su investigación pasa a docs/research/.", classes="muted")
        with Vertical(classes="form card"):
            yield Label("¿Qué tienes en mente? (opcional)")
            with Horizontal(classes="inline-row"):
                yield Input(placeholder="Algo con zombies… o déjalo vacío y que Claude proponga", id="id-hint",
                            max_length=200)
                yield Button("✦ Explorar idea", id="id-explore", variant="primary")
            yield Checkbox("Abrir Claude Code al crearla (investigación de mercado y 3 conceptos en IDEA.md)",
                           value=True, id="id-launch")
        yield Label("Ideas guardadas", classes="subtitle")
        yield DataTable(id="id-table", cursor_type="row", zebra_stripes=True)
        with Horizontal(classes="button-row"):
            yield Button("▶ Abrir en Claude Code", id="id-open")
            yield Button("✚ Convertir en juego", id="id-convert")
            yield Button("Carpeta", id="id-folder")

    def on_mount(self) -> None:
        table = self.query_one("#id-table", DataTable)
        table.add_column("Idea")
        table.add_column("Título")
        table.add_column("Estado")
        table.add_column("Modificada")
        self.ronavi_refresh(None)

    def ronavi_refresh(self, message: object) -> None:
        from ronavi.ui.app import EnvChanged
        if isinstance(message, EnvChanged):
            return
        table = self.query_one("#id-table", DataTable)
        current = self.selected()
        table.clear()
        for idea in self.rapp.ideas:
            state = (Text(f"→ {idea.converted_to}", style="#5ed6a0") if idea.converted_to else
                     Text("IDEA.md", style="#ffb37a") if idea.has_notes else Text("sin investigar", style="#8b8597"))
            table.add_row(idea.id, Text(idea.title, style="bold"), state, ago(idea.modified), key=idea.id)
        if current:
            try:
                table.move_cursor(row=table.get_row_index(current.id))
            except Exception:
                pass
        for bid in ("#id-open", "#id-convert", "#id-folder"):
            self.query_one(bid, Button).disabled = not self.rapp.ideas

    def selected(self) -> Idea | None:
        table = self.query_one("#id-table", DataTable)
        if not table.row_count:
            return None
        try:
            key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        except Exception:
            return None
        return next((i for i in self.rapp.ideas if i.id == key), None)

    @on(Button.Pressed, "#id-explore")
    @on(Input.Submitted, "#id-hint")
    def explore(self, _event: object = None) -> None:
        app = self.rapp
        hint_input = self.query_one("#id-hint", Input)
        hint = hint_input.value
        try:
            idea = create_idea(app.studio, hint)
        except (GuardError, OSError) as exc:
            app.notify(str(exc), title="No se creó la idea", severity="error")
            return
        hint_input.value = ""
        app.reload_games()
        if self.query_one("#id-launch", Checkbox).value:
            app.open_idea(idea, prompt=T.idea_prompt(hint))
        else:
            app.notify(f"Idea creada en {idea.root}", title="Idea")

    @on(DataTable.RowSelected, "#id-table")
    @on(Button.Pressed, "#id-open")
    def open_idea(self, _event: object = None) -> None:
        if idea := self.selected():
            prompt = None if idea.has_notes else T.idea_prompt(idea.hint)
            self.rapp.open_idea(idea, prompt=prompt)

    @on(Button.Pressed, "#id-convert")
    def convert(self) -> None:
        if idea := self.selected():
            self.screen.show_section("new")
            self.screen.query_one("#new", NewGameSection).use_idea(idea)

    @on(Button.Pressed, "#id-folder")
    def action_folder(self) -> None:
        if idea := self.selected():
            open_folder(idea.root)


# ============================================================================ new game

NO_IDEA = ""


class NewGameSection(Section):
    def compose(self) -> ComposeResult:
        yield Label("Nuevo juego", classes="section-title")
        yield Static("Cada juego vive en su propia carpeta, con su git, su CLAUDE.md, sus permisos y un guardián "
                     "que impide que Claude toque la plantilla u otros juegos. ¿Sin nombre todavía? Empieza en "
                     "✦ Ideas.", classes="muted")
        with Vertical(classes="form card"):
            yield Label("Nombre")
            yield Input(placeholder="Coin Dash", id="ng-name", max_length=40)
            yield Static("", id="ng-preview", classes="muted")
            yield Label("Género")
            yield Select([(label, key) for key, label in T.GENRES], value="obby", allow_blank=False, id="ng-genre")
            yield Label("La idea en una frase (opcional)")
            yield Input(placeholder="Recoge monedas mientras esquivas lava en un mundo de caramelo", id="ng-desc",
                        max_length=200)
            yield Label("Basado en una idea explorada (opcional: su investigación se copia a docs/research/)")
            yield Select([("Ninguna: empezar desde cero", NO_IDEA)], value=NO_IDEA, allow_blank=False, id="ng-idea")
            yield Checkbox("Repositorio git propio", value=True, id="ng-git")
            yield Checkbox("Commit inicial", value=True, id="ng-commit")
            yield Checkbox("Generar ya el proyecto de código (roblox-code · new_project.py)", value=False,
                           id="ng-code")
            yield Checkbox("Abrir Claude Code al terminar, con la etapa 1 (investigación y plan)", value=True,
                           id="ng-open")
            with Horizontal(classes="button-row"):
                yield Button("✚ Crear juego", id="ng-create", variant="primary")

    def on_mount(self) -> None:
        if not scaffold_script().exists():
            code = self.query_one("#ng-code", Checkbox)
            code.disabled = True
            code.label = "Generar ya el proyecto de código (requiere instalar las skills de SyphoDev)"
        self.ronavi_refresh(None)
        self._preview()

    def ronavi_refresh(self, _message: object) -> None:
        select = self.query_one("#ng-idea", Select)
        current = select.value
        options = [("Ninguna: empezar desde cero", NO_IDEA)]
        for idea in self.rapp.ideas:
            done = f" (ya es {idea.converted_to})" if idea.converted_to else ""
            options.append((f"{idea.id} · {idea.title}{done}", idea.id))
        select.set_options(options)
        select.value = current if any(v == current for _, v in options) else NO_IDEA

    def selected_idea(self) -> Idea | None:
        value = self.query_one("#ng-idea", Select).value
        return next((i for i in self.rapp.ideas if i.id == value), None)

    def use_idea(self, idea: Idea) -> None:
        """Ideas → Convertir en juego: preselect the idea and suggest its title as the name."""
        self.query_one("#ng-idea", Select).value = idea.id
        name = self.query_one("#ng-name", Input)
        if not name.value.strip():
            try:
                name.value = validate_name(idea.title)[0]
            except GuardError:
                pass
        name.focus()

    @on(Input.Changed, "#ng-name")
    def _preview(self, _event: object = None) -> None:
        name = self.query_one("#ng-name", Input).value
        preview = self.query_one("#ng-preview", Static)
        if not name.strip():
            preview.update(Text(f"Se creará en {self.rapp.studio.games_home}{'/'}<Nombre>", style="#8b8597"))
            return
        try:
            _, slug = validate_name(name)
            target = self.rapp.studio.games_home / slug
            if target.exists():
                preview.update(Text(f"✘ {target} ya existe", style="#ff5d6c"))
            else:
                preview.update(Text(f"✔ {target}", style="#5ed6a0"))
        except GuardError as exc:
            preview.update(Text(f"✘ {exc}", style="#ff5d6c"))

    @on(Checkbox.Changed, "#ng-git")
    def _git_toggle(self, event: Checkbox.Changed) -> None:
        commit = self.query_one("#ng-commit", Checkbox)
        commit.disabled = not event.value
        if not event.value:
            commit.value = False

    @on(Button.Pressed, "#ng-create")
    @on(Input.Submitted, "#ng-name")
    @on(Input.Submitted, "#ng-desc")
    def create(self, _event: object = None) -> None:
        app = self.rapp
        name = self.query_one("#ng-name", Input).value
        try:
            display, slug = validate_name(name)
        except GuardError as exc:
            app.notify(str(exc), severity="error")
            self.query_one("#ng-name", Input).focus()
            return
        genre = str(self.query_one("#ng-genre", Select).value)
        desc = self.query_one("#ng-desc", Input).value
        opts = {k: self.query_one(f"#ng-{k}", Checkbox).value for k in ("git", "commit", "code", "open")}
        idea = self.selected_idea()
        created: dict[str, Game] = {}

        def job(log) -> None:
            created["game"] = create_game(app.studio, display, genre, desc, init_git=opts["git"],
                                          commit=opts["commit"] and opts["git"], scaffold=opts["code"],
                                          from_idea=idea.root if idea else None, progress=log)

        def after(ok: bool) -> None:
            game = created.get("game")
            if not ok or not game:
                return
            self.query_one("#ng-name", Input).value = ""
            self.query_one("#ng-desc", Input).value = ""
            self.query_one("#ng-idea", Select).value = NO_IDEA
            app.studio.config.last_game = game.slug
            app.save_config()
            self.screen.show_section("projects")
            if opts["open"]:
                app.open_game(game, prompt=T.first_prompt(game.name, game.slug, genre, desc,
                                                          has_research=idea is not None))

        app.run_task(f"Creando {display}", [Job(f"Crear {slug}", func=job)], after)


# ============================================================================ skills

class SkillsSection(Section):
    def compose(self) -> ComposeResult:
        yield Label("Skills", classes="section-title")
        yield Static("Fijadas por commit en skills.lock.json. Las del estudio están disponibles en cada juego "
                     "(RoNavi abre Claude Code con --add-dir hacia el estudio).", classes="muted")
        yield DataTable(id="sk-table", cursor_type="row", zebra_stripes=True)
        with Horizontal(classes="button-row"):
            yield Button("Instalar / sincronizar", id="sk-sync", variant="primary")
            yield Button("Buscar actualizaciones", id="sk-update")
            yield Button("Configurar LOCAL.md", id="sk-local")
            yield Button("Recargar", id="sk-reload")

    def on_mount(self) -> None:
        self.query_one("#sk-table", DataTable).add_columns("Skill", "Fuente", "Ámbito", "Estado", "Para qué")
        self.ronavi_refresh(None)

    def ronavi_refresh(self, _message: object) -> None:
        table = self.query_one("#sk-table", DataTable)
        table.clear()
        plugin_rows = {c.name: c for c in self.rapp.checks if c.group == "Plugins"}
        try:
            items = skills.inventory(self.rapp.studio)
        except (OSError, ValueError) as exc:
            self.app.notify(f"No se pudo leer skills.lock.json: {exc}", severity="error")
            return
        for s in items:
            if s.scope == "plugin":
                row = plugin_rows.get(s.name)
                state = (Text("…", style="#8b8597") if row is None else
                         Text("✔ activo", style="#5ed6a0") if row.status == envmod.OK else
                         Text(f"✘ {row.detail}", style="#ff5d6c"))
            else:
                state = Text("✔ instalada", style="#5ed6a0") if s.installed else Text("✘ falta", style="#ff5d6c")
            table.add_row(Text(s.name, style="bold"), s.source, s.scope, state, s.description or "—")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        app = self.rapp
        studio = app.studio
        py = envmod.system_python()
        sync = str(studio.root / "scripts" / "skills_sync.py")
        bid = event.button.id
        if bid == "sk-sync":
            jobs = [Job(f"skills_sync {c}", cmd=[py, sync, c], cwd=studio.root)
                    for c in ("vendor", "user", "project", "plugins", "local-settings")]
            app.confirm("Instalar / sincronizar skills",
                        "Clona o actualiza vendor/ en los commits fijados, instala SyphoDev en ~/.claude (solo si "
                        "cambió), copia las skills de proyecto e instala los plugins. No mueve ningún commit fijado.",
                        lambda: app.run_task("Skills", jobs, lambda ok: self.ronavi_refresh(None)))
        elif bid == "sk-update":
            if envmod.SYSTEM == "Windows":
                cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                       str(studio.root / "scripts" / "update-skills.ps1")]
            else:
                cmd = ["bash", str(studio.root / "scripts" / "update-skills.sh")]
            app.confirm("Buscar actualizaciones",
                        "Muestra qué cambió en cada fuente y te pregunta en la terminal antes de mover cada commit "
                        "fijado. Si cambia algo, reinstala.",
                        lambda: (app.run_interactive(cmd, studio.root, title="Actualizar skills"),
                                 app.refresh_env()))
        elif bid == "sk-local":
            app.confirm("Configurar LOCAL.md",
                        "Se abre Claude Code en el estudio con /roblox-skills-setup: escribe las rutas de Blender, "
                        "la librería de VFX, etc. en el LOCAL.md de cada skill. Sal con /exit.",
                        lambda: app.open_claude_in_studio("/roblox-skills-setup", "Configurar LOCAL.md"))
        elif bid == "sk-reload":
            app.refresh_env()


# ============================================================================ tools

class ToolsSection(Section):
    def compose(self) -> ComposeResult:
        yield Label("Herramientas", classes="section-title")
        yield Static("Diagnóstico completo de scripts/doctor.py. Los valores de las claves nunca se muestran.",
                     classes="muted")
        yield DataTable(id="tl-table", cursor_type="row", zebra_stripes=True)
        with Horizontal(classes="button-row"):
            yield Button("Instalar programas", id="tl-install", variant="primary")
            yield Button("Instalar opcionales", id="tl-optional")
            yield Button("Dependencias de Python", id="tl-pip")
            yield Button("Repetir diagnóstico", id="tl-doctor")

    def on_mount(self) -> None:
        self.query_one("#tl-table", DataTable).add_columns(" ", "Grupo", "Comprobación", "Detalle", "Cómo arreglarlo")
        self.ronavi_refresh(None)

    def ronavi_refresh(self, _message: object) -> None:
        table = self.query_one("#tl-table", DataTable)
        table.clear()
        if self.rapp.checks_loading:
            table.add_row("…", "", "Comprobando…", "", "")
        for c in self.rapp.checks:
            icon, color = STATUS_ICON.get(c.status, ("?", "#8b8597"))
            table.add_row(Text(icon, style=f"bold {color}"), c.group, c.name, c.detail[:70], c.fix[:80])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        app = self.rapp
        studio = app.studio
        bid = event.button.id
        if bid in ("tl-install", "tl-optional"):
            optional = bid == "tl-optional"
            step = next(s for s in envmod.setup_steps(studio, optional) if s.key == "programs")
            if step.kind == "manual":
                app.push_screen(TextScreen("Programas", "\n".join(step.manual)))
                return
            app.confirm("Instalar programas", step.why + ("\n\nIncluye los opcionales." if optional else "") +
                        "\n\nRoNavi se suspende mientras winget trabaja; lo ya instalado se salta.",
                        lambda: (app.run_interactive(step.commands[0], studio.root, title="Instalar programas"),
                                 app.refresh_env()))
        elif bid == "tl-pip":
            step = next(s for s in envmod.setup_steps(studio) if s.key == "pydeps")
            app.confirm(step.title, step.why, lambda: app.run_task(step.title, [
                Job(step.title, cmd=step.commands[0], cwd=studio.root)]))
        elif bid == "tl-doctor":
            app.refresh_env()


# ============================================================================ integrations

class IntegrationsSection(Section):
    def compose(self) -> ComposeResult:
        yield Label("Integraciones", classes="section-title")
        yield Label("Servidores MCP", classes="subtitle")
        yield Static("Un solo servidor MCP de Studio a la vez: encender uno apaga el otro. Se guarda en el "
                     "settings.local.json (no versionado) del ámbito elegido.", classes="muted")
        yield Select([("Estudio (raíz)", "__studio__")], value="__studio__", allow_blank=False, id="mcp-scope")
        for name, label, note in integrations.MCP_SERVERS:
            with Horizontal(classes="switch-row"):
                yield Switch(id=f"mcp-{name}")
                yield Static(Text.assemble((label, "bold"), f"  {name}\n", (note, "#8b8597")))
        yield Label("Claves y variables de entorno", classes="subtitle")
        yield Static("Se guardan como variables de entorno de tu usuario: nunca en archivos ni en el chat."
                     if integrations.can_set_env() else
                     "En macOS/Linux añade cada una con export en tu ~/.zshrc o ~/.bashrc.", classes="muted")
        yield DataTable(id="key-table", cursor_type="row", zebra_stripes=True)
        with Horizontal(classes="button-row"):
            yield Button("Definir valor…", id="key-set", variant="primary", disabled=not integrations.can_set_env())
            yield Button("Autenticar Figma (/mcp)", id="int-figma")
            yield Button("Ver cupos", id="int-quota")
        yield Label("Roblox Studio (manual)", classes="subtitle")
        yield Static("• Assistant → … → Manage MCP Servers → Enable Studio as MCP server (indicador verde).\n"
                     "• Script Sync APAGADO: usamos Rojo.\n"
                     "• Revisa el interruptor del MCP después de cada actualización de Studio.", classes="card")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._loading = True

    def on_mount(self) -> None:
        self.query_one("#key-table", DataTable).add_columns("Variable", "Para qué", "Estado")
        self.ronavi_refresh(None)

    def project_dir(self) -> Path:
        value = self.query_one("#mcp-scope", Select).value
        if value == "__studio__":
            return self.rapp.studio.root
        return self.rapp.studio.games_home / str(value)

    def ronavi_refresh(self, _message: object) -> None:
        scope = self.query_one("#mcp-scope", Select)
        current = scope.value
        options = [("Estudio (raíz)", "__studio__")] + [(f"Juego: {g.name}", g.slug) for g in self.rapp.games
                                                        if g.managed]
        scope.set_options(options)
        scope.value = current if current in [v for _, v in options] else "__studio__"
        self._load_mcp()
        table = self.query_one("#key-table", DataTable)
        table.clear()
        for k in integrations.KEYS:
            state = integrations.key_status(k)
            style = "#5ed6a0" if state != "falta" else ("#8b8597" if k.optional else "#ff5d6c")
            table.add_row(Text(k.name, style="bold"), k.label + (" (opcional)" if k.optional else ""),
                          Text(state, style=style), key=k.name)

    def _load_mcp(self) -> None:
        self._loading = True
        state = integrations.mcp_state(self.project_dir())
        for name, _, _ in integrations.MCP_SERVERS:
            self.query_one(f"#mcp-{name}", Switch).value = state.get(name, False)
        self.call_after_refresh(setattr, self, "_loading", False)

    @on(Select.Changed, "#mcp-scope")
    def _scope_changed(self, _: Select.Changed) -> None:
        self._load_mcp()

    @on(Switch.Changed)
    def _switch(self, event: Switch.Changed) -> None:
        if self._loading or not event.switch.id or not event.switch.id.startswith("mcp-"):
            return
        name = event.switch.id[4:]
        project = self.project_dir()
        if integrations.mcp_state(project).get(name) == event.value:
            return  # programmatic update, nothing to change
        try:
            if not same_path(project, self.rapp.studio.root):
                scope_for(self.rapp.studio, project).check(project / ".claude" / "settings.local.json")
            msgs = integrations.set_mcp(project, name, event.value)
        except (GuardError, OSError, ValueError) as exc:
            self.app.notify(str(exc), severity="error")
            return
        self.app.notify("\n".join(msgs), title="MCP")
        self._load_mcp()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        app = self.rapp
        bid = event.button.id
        if bid == "key-set":
            table = self.query_one("#key-table", DataTable)
            try:
                name = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
            except Exception:
                return
            info = next(k for k in integrations.KEYS if k.name == name)

            def save(value: str | None) -> None:
                if value is None:
                    return
                try:
                    integrations.set_user_env(info.name, value)
                except (OSError, ValueError) as exc:
                    app.notify(str(exc), severity="error")
                    return
                app.notify(f"{info.name} {'guardada' if value.strip() else 'borrada'}. Las terminales nuevas "
                           "(y Claude Code abierto desde RoNavi) la verán.", title="Variables")
                self.ronavi_refresh(None)
            app.push_screen(SecretScreen(info.name, info.label, info.secret), save)
        elif bid == "int-figma":
            app.confirm("Autenticar Figma", "Se abre Claude Code en el estudio. Escribe /mcp, elige figma → "
                        "Authenticate y completa el login en el navegador. Sal con /exit.",
                        lambda: app.open_claude_in_studio(None, "Autenticar Figma"))
        elif bid == "int-quota":
            self._quota()

    @work(thread=True, exclusive=True, group="quota")
    def _quota(self) -> None:
        text = integrations.quota_status(self.rapp.studio)
        self.app.call_from_thread(self.app.push_screen, TextScreen("Cupos (quota-guard)", text))


# ============================================================================ settings

class SettingsSection(Section):
    def compose(self) -> ComposeResult:
        studio = self.rapp.studio
        yield Label("Configuración", classes="section-title")
        with Vertical(classes="form card"):
            yield Label("Carpeta de juegos")
            yield Input(value=str(studio.games_home), id="st-home")
            yield Static("Por defecto, games/ dentro del estudio. No puede ser el estudio ni estar dentro de un "
                         "juego.", classes="muted")
            yield Label("Al abrir Claude Code")
            with RadioSet(id="st-mode"):
                yield RadioButton("En esta terminal (RoNavi se suspende y vuelve al salir)",
                                  value=studio.config.launch_mode == "here", id="st-here")
                yield RadioButton("En una ventana nueva", value=studio.config.launch_mode == "window",
                                  id="st-window")
            with Horizontal(classes="switch-row"):
                yield Switch(value=studio.config.animations, id="st-anim")
                yield Static("Animaciones de Navi")
            with Horizontal(classes="button-row"):
                yield Button("Guardar", id="st-save", variant="primary")
                yield Button("Asistente de instalación", id="st-wizard")
                yield Button("Añadir 'ronavi' al PATH", id="st-path")
                yield Button("Revisar guardianes", id="st-guards")
                yield Button("Actualizar RoNavi", id="st-update")
        yield Label("Acerca de", classes="subtitle")
        yield Static("", id="st-about", classes="card")

    def on_mount(self) -> None:
        self.ronavi_refresh(None)

    def ronavi_refresh(self, _message: object) -> None:
        studio = self.rapp.studio
        t = Text()
        rev = updates.describe(studio.root)
        t.append(f"RoNavi Studio {__version__}", style="bold #ff8a3d")
        t.append(f"  ({rev})\n" if rev else "\n", style="#8b8597")
        t.append(f"Estudio:       {studio.root}\n")
        t.append(f"Juegos:        {studio.games_home}\n")
        t.append(f"Claude Code:   {claude_executable() or 'no encontrado'}\n")
        t.append(f"Python:        {envmod.system_python()}\n")
        t.append(f"'ronavi' en PATH: {'sí' if integrations.ronavi_on_path(studio) else 'no'}\n")
        self.query_one("#st-about", Static).update(t)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        app = self.rapp
        studio = app.studio
        bid = event.button.id
        if bid == "st-save":
            self.save()
        elif bid == "st-wizard":
            from ronavi.ui.wizard import WizardScreen
            app.push_screen(WizardScreen())
        elif bid == "st-path":
            app.confirm("Añadir 'ronavi' al PATH",
                        f"Podrás escribir ronavi en cualquier terminal nueva. Se añade {studio.root} a la variable PATH "
                        "de tu usuario." if envmod.SYSTEM == "Windows" else
                        "Se crea el enlace ~/.local/bin/ronavi hacia el lanzador del estudio.",
                        lambda: (app.notify(integrations.add_to_user_path(studio.root), title="PATH"),
                                 self.ronavi_refresh(None)))
        elif bid == "st-update":
            def run_update() -> None:
                app.run_task("Actualizar RoNavi",
                             [Job("git fetch y actualizar", func=lambda log: log(updates.update(studio, log)))],
                             lambda _ok: self.ronavi_refresh(None))
            app.confirm("Actualizar RoNavi",
                        "Descarga la última versión del estudio con git. Tus juegos, ideas y configuración no se "
                        "tocan. Si el estudio tiene cambios sin guardar, no se actualiza.", run_update)
        elif bid == "st-guards":
            app.run_task("Guardianes", [Job("Sincronizar el guardián de todos los juegos",
                                            func=lambda log: [log("! " + p) for p in sync_all_guards(studio, log)])])

    def save(self) -> None:
        app = self.rapp
        studio = app.studio
        raw = self.query_one("#st-home", Input).value.strip()
        home = Path(raw).expanduser().resolve() if raw else studio.default_games_home
        if same_path(home, studio.root) or is_within(studio.root, home):
            app.notify("La carpeta de juegos no puede ser ni contener el estudio.", severity="error")
            return
        if any(is_within(home, g.root) for g in app.games):
            app.notify("La carpeta de juegos no puede estar dentro de un juego.", severity="error")
            return
        mode = "window" if self.query_one("#st-window", RadioButton).value else "here"

        def apply() -> None:
            home.mkdir(parents=True, exist_ok=True)
            studio.config.games_home = None if same_path(home, studio.default_games_home) else str(home)
            studio.config.launch_mode = mode
            studio.config.animations = self.query_one("#st-anim", Switch).value
            app.save_config()
            app.reload_games()
            self.ronavi_refresh(None)
            app.notify("Configuración guardada.", title="Listo")
            if integrations.can_set_env() and not same_path(integrations.user_env("ROBLOX_GAMES_HOME") or ".",
                                                            home):
                app.notify("Recuerda actualizar ROBLOX_GAMES_HOME en el Asistente para las skills.",
                           severity="warning", timeout=8)

        if not home.exists():
            app.confirm("Crear carpeta", f"{home} no existe. ¿Crearla y usarla para los juegos?", apply)
        else:
            apply()


# ============================================================================ main screen

class MainScreen(Screen[None]):
    BINDINGS = [
        *(Binding(str(i + 1), f"section('{key}')", label, show=False) for i, (key, label) in enumerate(SECTIONS)),
        Binding("ctrl+n", "section('new')", "Nuevo juego"),
        Binding("f5", "refresh_all", "Recargar"),
        Binding("question_mark", "help", "Ayuda"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal(id="main"):
            with Vertical(id="sidebar"):
                with Horizontal(id="brand"):
                    yield Static(mascot.fox("mini"), id="brand-fox")
                    yield Static(Text.assemble(("RoNavi\n", "bold #ff8a3d"), ("Studio", "bold #ece6f0"),
                                               (f"\nv{__version__}", "#8b8597")), id="brand-name")
                yield OptionList(*(Option(f"{label}", id=key) for key, label in SECTIONS), id="nav")
                yield Static("", id="env-pill")
                yield Static("1-8 secciones · ? ayuda", classes="muted nav-hint")
            with ContentSwitcher(id="content", initial="home"):
                yield HomeSection(id="home")
                yield ProjectsSection(id="projects")
                yield IdeasSection(id="ideas")
                yield NewGameSection(id="new")
                yield SkillsSection(id="skills")
                yield ToolsSection(id="tools")
                yield IntegrationsSection(id="integrations")
                yield SettingsSection(id="settings")
        yield Footer()

    def on_mount(self) -> None:
        self.ronavi_refresh(None)
        nav = self.query_one("#nav", OptionList)
        nav.highlighted = 0
        nav.focus()

    def ronavi_refresh(self, _message: object) -> None:
        app = self.app
        pill = self.query_one("#env-pill", Static)
        if getattr(app, "checks_loading", False) or not getattr(app, "checks", None):
            pill.update(Text("● comprobando…", style="#8b8597"))
            return
        ok, warn, fail = envmod.counts(app.checks)  # type: ignore[attr-defined]
        pill.update(Text.assemble(("● ", "#5ed6a0" if not fail else "#ff5d6c"), f"{ok} ✔  {warn} !  {fail} ✘"))

    @on(OptionList.OptionHighlighted, "#nav")
    def _nav(self, event: OptionList.OptionHighlighted) -> None:
        if event.option.id:
            self.query_one("#content", ContentSwitcher).current = event.option.id

    @on(OptionList.OptionSelected, "#nav")
    def _nav_enter(self, event: OptionList.OptionSelected) -> None:
        section = self.query_one(f"#{event.option.id}")
        focusables = [w for w in section.query("*") if w.focusable]
        if focusables:
            focusables[0].focus()

    def show_section(self, key: str) -> None:
        nav = self.query_one("#nav", OptionList)
        nav.highlighted = [k for k, _ in SECTIONS].index(key)
        self.query_one("#content", ContentSwitcher).current = key
        if key == "new":
            self.query_one("#ng-name", Input).focus()
        elif key == "ideas":
            self.query_one("#id-hint", Input).focus()

    def action_section(self, key: str) -> None:
        self.show_section(key)

    def action_refresh_all(self) -> None:
        self.app.reload_games()  # type: ignore[attr-defined]
        self.app.refresh_env()  # type: ignore[attr-defined]

    def action_help(self) -> None:
        self.app.push_screen(TextScreen("Atajos de RoNavi Studio", HELP))


HELP = """Navegación
  1-8          Ir a una sección (Inicio, Proyectos, Ideas, Nuevo juego, Skills, Herramientas, Integraciones, Configuración)
  Tab          Siguiente control        Mayús+Tab   Anterior
  Ctrl+N       Nuevo juego              F5          Recargar juegos y diagnóstico

Ideas
  Explorar idea  Claude investiga sin nombre, género ni git, en work/ideas/<fecha>, y escribe IDEA.md
  Enter          Abrir la idea seleccionada en Claude Code       F   Abrir su carpeta
  Convertir      Crea el juego basado en la idea: su investigación va a docs/research/
  Ctrl+P       Paleta de comandos       Ctrl+Q      Salir

Proyectos
  Enter        Abrir Claude Code en el juego (con las skills del estudio y el guardián activo)
  W            Abrir en una ventana nueva
  F / V        Abrir la carpeta / VS Code
  G            Reinstalar el guardián del juego
  A            Adoptar una carpeta que no creó RoNavi
  C            Ejecutar check.py (rojo build, lune, selene, stylua)

Protecciones
  • Cada juego tiene su propio git: RoNavi no ejecuta git en un juego cuyo repositorio sea otro.
  • Un guardián (hook PreToolUse) bloquea cualquier escritura de Claude fuera del juego que esté
    dentro de la plantilla o de otro juego, también por Bash o PowerShell.
  • Reglas deny de Edit para la plantilla y los demás juegos, regeneradas al abrir cada juego.
  • Toda escritura de RoNavi pasa por una comprobación de rutas que resuelve enlaces y junctions.
"""
