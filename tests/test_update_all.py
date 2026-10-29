""""Actualizar todo" with every subprocess simulated: claude, rokit and update-skills never run for real."""

import sys
import types
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from ronavi.core import update_all
from ronavi.core.projects import create_game
from tests.helpers import StudioTestCase

PINNED = [{"name": "roblox-skills", "ref": "v1.1.0"}, {"name": "claude-plugins-official"}]


class FakeProcs:
    """Stands in for update_all's subprocess helpers and records every command."""

    def __init__(self, markets=PINNED, fail=()):
        self.markets, self.fail = markets, fail
        self.calls: list[tuple[list[str], Path]] = []
        self.interactive: list[list[str]] = []

    def run(self, cmd, cwd, progress, env=None):
        self.calls.append((list(cmd), Path(cwd)))
        return 1 if any(f in " ".join(cmd) for f in self.fail) else 0

    def json(self, cmd, cwd):
        return self.markets

    def terminal(self, cmd, cwd):
        self.interactive.append(list(cmd))
        return 0

    def commands(self) -> list[str]:
        return [" ".join(c) for c, _ in self.calls]

    def patch(self, stack: ExitStack, toolchain=None) -> None:
        """toolchain=None simulates the module not existing yet (ImportError)."""
        stack.enter_context(mock.patch.object(update_all, "_run", self.run))
        stack.enter_context(mock.patch.object(update_all, "_json", self.json))
        stack.enter_context(mock.patch.object(update_all, "claude_executable", lambda: "claude"))
        stack.enter_context(mock.patch.dict(sys.modules, {"ronavi.core.toolchain": toolchain}))


class UpdateAllTests(StudioTestCase):
    def setUp(self):
        super().setUp()
        self.game = create_game(self.studio, "Coin Dash", "obby", "", init_git=False, commit=False).root
        (self.game / "aftman.toml").write_text('[tools]\nrojo = "rojo-rbx/rojo@7.4.0"\n', encoding="utf-8")
        create_game(self.studio, "No Tools", "obby", "", init_git=False, commit=False)  # no manifest: skipped

    def run_all(self, fake: FakeProcs, toolchain=None) -> dict[str, update_all.StepResult]:
        lines: list[str] = []
        with ExitStack() as stack:
            fake.patch(stack, toolchain)
            results = update_all.update_all(self.studio, fake.terminal, lines.append)
        self.log = "\n".join(lines)
        self.assertEqual([r.title for r in results], ["RoNavi", "Skills de terceros", "Plugins de Claude Code",
                                                      "Guardianes de los juegos", "Toolchain de los juegos"])
        return {r.title: r for r in results}

    def test_every_step_runs_even_when_the_first_fails(self):
        fake = FakeProcs()
        res = self.run_all(fake)
        # The test studio has no origin: the RoNavi step fails and the rest still run.
        self.assertEqual(res["RoNavi"].status, update_all.FAIL)
        self.assertIn("origin", res["RoNavi"].detail)
        self.assertEqual(res["Skills de terceros"].status, update_all.OK)
        self.assertTrue(any("update-skills" in part for part in fake.interactive[0]))
        self.assertEqual(res["Plugins de Claude Code"].status, update_all.OK)
        cmds = fake.commands()
        self.assertIn("claude plugin marketplace update roblox-skills", cmds)
        self.assertIn("claude plugin update roblox-skills@roblox-skills --scope project", cmds)
        self.assertIn("claude plugin update figma@claude-plugins-official --scope project", cmds)
        self.assertFalse([c for c in cmds if " add " in c or " remove " in c])  # the EL4CTEO tag never moves
        self.assertEqual(res["Guardianes de los juegos"].status, update_all.OK)
        self.assertIn("2 juegos", res["Guardianes de los juegos"].detail)
        # No ronavi.core.toolchain yet: pending, but rokit install still ran where there is a manifest.
        self.assertEqual(res["Toolchain de los juegos"].status, update_all.PENDING)
        self.assertEqual([cwd for c, cwd in fake.calls if c[:2] == ["rokit", "install"]], [self.game])
        self.assertIn("✘ RoNavi", self.log)
        self.assertIn("… Toolchain de los juegos", self.log)

    def test_a_marketplace_off_its_pin_is_reported_not_moved(self):
        fake = FakeProcs(markets=[{"name": "roblox-skills", "ref": "main"}, {"name": "claude-plugins-official"}])
        res = self.run_all(fake)
        plugins = res["Plugins de Claude Code"]
        self.assertEqual(plugins.status, update_all.FAIL)
        self.assertIn("v1.1.0", plugins.detail)
        cmds = fake.commands()
        self.assertFalse([c for c in cmds if "roblox-skills" in c])
        self.assertIn("claude plugin update figma@claude-plugins-official --scope project", cmds)

    def test_toolchain_module_raises_versions_then_rokit_installs(self):
        seen = []

        def upgrade_toolchain(game_root, progress):
            seen.append(Path(game_root))
            return ["rojo 7.4.0 → 7.5.1"]

        module = types.ModuleType("ronavi.core.toolchain")
        module.upgrade_toolchain = upgrade_toolchain
        fake = FakeProcs()
        res = self.run_all(fake, toolchain=module)
        self.assertEqual(seen, [self.game])
        self.assertEqual(res["Toolchain de los juegos"].status, update_all.OK)
        self.assertIn("1 con versiones nuevas", res["Toolchain de los juegos"].detail)
        self.assertIn("rojo 7.4.0 → 7.5.1", self.log)
        self.assertIn("rokit install", fake.commands())

    def test_failures_are_reported_per_step(self):
        def broken(game_root, progress):
            raise ValueError("aftman.toml roto")

        module = types.ModuleType("ronavi.core.toolchain")
        module.upgrade_toolchain = broken
        fake = FakeProcs(fail=("figma",))
        fake.terminal = lambda cmd, cwd: 2  # the user's update-skills run failed
        res = self.run_all(fake, toolchain=module)
        self.assertEqual(res["Skills de terceros"].status, update_all.FAIL)
        self.assertIn("código 2", res["Skills de terceros"].detail)
        self.assertEqual(res["Plugins de Claude Code"].status, update_all.FAIL)
        self.assertIn("figma", res["Plugins de Claude Code"].detail)
        self.assertEqual(res["Toolchain de los juegos"].status, update_all.FAIL)
        self.assertIn("CoinDash: aftman.toml roto", res["Toolchain de los juegos"].detail)
        self.assertNotIn("rokit install", fake.commands())  # a broken upgrade is not installed

    def test_without_claude_the_plugin_step_fails_cleanly(self):
        fake = FakeProcs()
        with ExitStack() as stack:
            fake.patch(stack)
            stack.enter_context(mock.patch.object(update_all, "claude_executable", lambda: None))
            result = update_all.run_step(update_all.steps(self.studio, fake.terminal)[2])
        self.assertEqual(result.status, update_all.FAIL)
        self.assertIn("Claude Code no está instalado", result.detail)
        self.assertEqual(fake.calls, [])
