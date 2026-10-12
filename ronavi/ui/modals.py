"""Dialogs: confirm, secret input, long text and the live task log."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, LoadingIndicator, RichLog, Static

from ronavi.ui import mascot


class ConfirmScreen(ModalScreen[bool]):
    """Yes/No for anything important. Enter never confirms by accident: the focus starts on 'No'."""

    BINDINGS = [Binding("escape", "answer(False)", "Cancelar"), Binding("y,s", "answer(True)", "Sí", show=False),
                Binding("n", "answer(False)", "No", show=False)]

    def __init__(self, title: str, body: str, yes: str = "Sí, continuar", danger: bool = False):
        super().__init__()
        self.title_text, self.body, self.yes, self.danger = title, body, yes, danger

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self.title_text, classes="dialog-title")
            yield Static(self.body, classes="dialog-body", markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button("No", id="no")
                yield Button(self.yes, id="yes", variant="error" if self.danger else "primary")

    def on_mount(self) -> None:
        self.query_one("#no", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_answer(self, value: bool) -> None:
        self.dismiss(value)


class SecretScreen(ModalScreen["str | None"]):
    """Masked input for an API key. The value goes straight to the user environment."""

    BINDINGS = [Binding("escape", "cancel", "Cancelar")]

    def __init__(self, name: str, label: str, secret: bool):
        super().__init__()
        self.var, self.label, self.secret = name, label, secret

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(f"Definir {self.var}", classes="dialog-title")
            yield Static(f"{self.label}\n\nSe guarda como variable de entorno de tu usuario de Windows. "
                         "No se escribe en ningún archivo, no se muestra y no llega a Claude. "
                         "Déjalo vacío para borrarla.", classes="dialog-body", markup=False)
            yield Input(password=self.secret, placeholder="valor", id="value")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cancelar", id="cancel")
                yield Button("Guardar", id="save", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#value", Input).focus()

    def on_input_submitted(self, _: Input.Submitted) -> None:
        self.dismiss(self.query_one("#value", Input).value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(self.query_one("#value", Input).value if event.button.id == "save" else None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class TextScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape,enter,q", "close", "Cerrar")]

    def __init__(self, title: str, text: str):
        super().__init__()
        self.title_text, self.text = title, text

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog wide"):
            yield Label(self.title_text, classes="dialog-title")
            with VerticalScroll(classes="text-scroll"):
                yield Static(self.text, markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cerrar", id="close", variant="primary")

    def on_button_pressed(self, _: Button.Pressed) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


@dataclass
class Job:
    """One unit of work for TaskScreen: a command to stream, or a Python function."""

    title: str
    cmd: list[str] | None = None
    func: Callable[[Callable[[str], None]], object] | None = None
    cwd: Path | None = None
    env: dict[str, str] | None = field(default=None, repr=False)


class TaskScreen(ModalScreen[bool]):
    """Runs jobs one after another in a thread and streams their output. Stops at the first failure."""

    BINDINGS = [Binding("escape", "close", "Cerrar")]

    def __init__(self, title: str, jobs: list[Job]):
        super().__init__()
        self.title_text, self.jobs = title, jobs
        self.done = False
        self.ok = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog wide task"):
            with Horizontal(classes="task-head"):
                yield Static(mascot.fox("mini", "normal"), classes="task-fox")
                with Vertical():
                    yield Label(self.title_text, classes="dialog-title")
                    yield Label("Trabajando…", id="task-status", classes="muted")
                    yield LoadingIndicator(id="task-spinner")
            yield RichLog(id="task-log", wrap=True, markup=False, highlight=False, max_lines=4000)
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cerrar", id="close", variant="primary", disabled=True)

    def on_mount(self) -> None:
        self.run_jobs()

    def log_line(self, line: str) -> None:
        self.query_one("#task-log", RichLog).write(line)

    @work(thread=True, exclusive=True)
    def run_jobs(self) -> None:
        ok = True
        for i, job in enumerate(self.jobs, 1):
            self.app.call_from_thread(self.log_line, f"\n▸ [{i}/{len(self.jobs)}] {job.title}")
            try:
                if job.func is not None:
                    job.func(lambda s: self.app.call_from_thread(self.log_line, s))
                elif job.cmd:
                    code = self._stream(job)
                    if code != 0:
                        self.app.call_from_thread(self.log_line, f"✗ terminó con código {code}")
                        ok = False
                        break
                self.app.call_from_thread(self.log_line, "✓ hecho")
            except Exception as exc:  # shown to the user, never swallowed
                self.app.call_from_thread(self.log_line, f"✗ {exc}")
                ok = False
                break
        self.app.call_from_thread(self._finish, ok)

    def _stream(self, job: Job) -> int:
        env = dict(job.env or os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.setdefault("PYTHONUTF8", "1")
        self.app.call_from_thread(self.log_line, "$ " + " ".join(job.cmd or []))
        proc = subprocess.Popen(job.cmd or [], cwd=job.cwd, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True,
                                encoding="utf-8", errors="replace", bufsize=1)
        assert proc.stdout is not None
        for line in proc.stdout:
            self.app.call_from_thread(self.log_line, line.rstrip("\r\n"))
        return proc.wait()

    def _finish(self, ok: bool) -> None:
        self.done, self.ok = True, ok
        self.query_one("#task-spinner", LoadingIndicator).display = False
        status = self.query_one("#task-status", Label)
        status.update("Terminado sin errores." if ok else "Se detuvo por un error: revisa el registro.")
        status.set_classes("ok" if ok else "bad")
        self.query_one(".task-fox", Static).update(mascot.fox("mini", "wink" if ok else "blink"))
        button = self.query_one("#close", Button)
        button.disabled = False
        button.focus()

    def on_button_pressed(self, _: Button.Pressed) -> None:
        self.action_close()

    def action_close(self) -> None:
        if self.done:
            self.dismiss(self.ok)
        else:
            self.app.notify("Espera a que termine la tarea.", severity="warning")
