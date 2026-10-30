"""Drive the real TUI headless with Textual's pilot. Skipped when Textual is not installed."""

import asyncio
import unittest

try:
    import textual  # noqa: F401
except ImportError:  # the core tests still run without the venv
    textual = None

from tests.helpers import StudioTestCase

if textual:
    from textual.widgets import Checkbox, ContentSwitcher, Input, Select

    from ronavi.ui import mascot
    from ronavi.ui.app import RoNaviApp
    from ronavi.ui.main import MainScreen
    from ronavi.ui.modals import TaskScreen, TextScreen
    from ronavi.ui.welcome import WelcomeScreen
    from ronavi.ui.wizard import WizardScreen


@unittest.skipIf(textual is None, "Textual not installed (run through ronavi's .venv)")
class TuiTests(StudioTestCase, unittest.IsolatedAsyncioTestCase):
    def make_app(self, first_run=False):
        self.studio.config.setup_done = not first_run
        self.studio.config.animations = False
        return RoNaviApp(self.studio, run_checks=False)

    async def wait_for(self, pilot, predicate, timeout=30.0):
        loop = asyncio.get_running_loop()
        end = loop.time() + timeout
        while not predicate():
            if loop.time() > end:
                self.fail("timed out waiting for the UI")
            await pilot.pause(0.1)

    async def test_welcome_then_main_and_every_section(self):
        app = self.make_app()
        async with app.run_test(size=(150, 48)) as pilot:
            self.assertIsInstance(app.screen, WelcomeScreen)
            await pilot.press("enter")
            self.assertIsInstance(app.screen, MainScreen)
            switcher = app.screen.query_one("#content", ContentSwitcher)
            for key, section in zip("12345678", ["home", "projects", "ideas", "new", "skills", "tools",
                                                  "integrations", "settings"]):
                app.screen.query_one("#nav").focus()
                await pilot.press(key)
                await pilot.pause()
                self.assertEqual(switcher.current, section)

    async def test_first_run_opens_the_wizard(self):
        app = self.make_app(first_run=True)
        async with app.run_test(size=(150, 48)) as pilot:
            await pilot.press("enter")  # leave the welcome screen
            self.assertIsInstance(app.screen, WizardScreen)
            self.assertGreaterEqual(len(app.screen.steps), 5)
            await pilot.press("escape")  # finish: asks to confirm when steps are pending, or closes
            await pilot.pause()

    async def test_wizard_optional_checkbox_rebuilds_steps(self):
        # Regression: toggling the checkbox crashed with DuplicateIds (clear() is asynchronous).
        app = self.make_app(first_run=True)
        async with app.run_test(size=(150, 48)) as pilot:
            await pilot.press("enter")
            wizard = app.screen
            self.assertIsInstance(wizard, WizardScreen)
            checkbox = wizard.query_one("#wiz-optional", Checkbox)
            for _ in range(3):
                checkbox.toggle()
                await pilot.pause(0.2)
            await pilot.click("#wiz-optional")
            await pilot.pause(0.3)
            self.assertIs(app.screen, wizard)
            steps = wizard.query_one("#wiz-steps")
            self.assertEqual(len(steps.children), len(wizard.steps))
            programs = next(s for s in wizard.steps if s.key == "programs")
            if programs.commands:
                self.assertEqual("-Optional" in programs.commands[0], checkbox.value)

    async def test_create_a_game_from_the_form(self):
        app = self.make_app()
        async with app.run_test(size=(150, 48)) as pilot:
            await pilot.press("enter")
            app.screen.show_section("new")
            await pilot.pause()
            app.screen.query_one("#ng-open", Checkbox).value = False  # never launch Claude in tests
            name = app.screen.query_one("#ng-name", Input)
            name.focus()
            await pilot.press(*"Lava Run")
            await pilot.press("enter")
            await self.wait_for(pilot, lambda: isinstance(app.screen, TaskScreen))
            await self.wait_for(pilot, lambda: app.screen.done, timeout=60)
            self.assertTrue(app.screen.ok)
            await pilot.press("escape")
            await pilot.pause()
            self.assertTrue((self.root / "games" / "LavaRun" / ".claude" / "hooks" / "ronavi_guard.py").exists())
            self.assertIn("LavaRun", [g.slug for g in app.games])
            self.assertEqual(app.screen.query_one("#content", ContentSwitcher).current, "projects")
            await app.workers.wait_for_complete()

    async def test_explore_an_idea_then_build_a_game_on_it(self):
        app = self.make_app()
        async with app.run_test(size=(150, 48)) as pilot:
            await pilot.press("enter")
            app.screen.query_one("#home-idea").press()
            await pilot.pause()
            switcher = app.screen.query_one("#content", ContentSwitcher)
            self.assertEqual(switcher.current, "ideas")
            self.assertTrue(app.screen.query_one("#id-hint", Input).has_focus)
            app.screen.query_one("#id-launch", Checkbox).value = False  # never launch Claude in tests
            await pilot.press(*"zombies", "enter")
            await pilot.pause(0.3)
            self.assertEqual(len(app.ideas), 1)
            idea = app.ideas[0]
            self.assertEqual(idea.hint, "zombies")
            (idea.root / "IDEA.md").write_text("# Zombie Farm\n", encoding="utf-8")
            app.reload_games()
            await pilot.pause()

            await pilot.click("#id-convert")
            await pilot.pause()
            self.assertEqual(switcher.current, "new")
            self.assertEqual(app.screen.query_one("#ng-idea", Select).value, idea.id)
            self.assertEqual(app.screen.query_one("#ng-name", Input).value, "Zombie Farm")  # from IDEA.md
            app.screen.query_one("#ng-open", Checkbox).value = False
            await pilot.click("#ng-create")
            await self.wait_for(pilot, lambda: isinstance(app.screen, TaskScreen))
            await self.wait_for(pilot, lambda: app.screen.done, timeout=60)
            self.assertTrue(app.screen.ok)
            await pilot.press("escape")
            await pilot.pause()
            game = self.root / "games" / "ZombieFarm"
            self.assertTrue((game / "docs" / "research" / "IDEA.md").is_file())
            self.assertEqual(app.screen.query_one("#ng-idea", Select).value, "")
            self.assertEqual(app.ideas[0].converted_to, "ZombieFarm")
            await app.workers.wait_for_complete()

    async def test_invalid_name_is_rejected_in_the_form(self):
        app = self.make_app()
        async with app.run_test(size=(150, 48)) as pilot:
            await pilot.press("enter")
            app.screen.show_section("new")
            await pilot.pause()
            app.screen.query_one("#ng-name", Input).value = "../escape"
            await pilot.click("#ng-create")
            await pilot.pause()
            self.assertIsInstance(app.screen, MainScreen)
            self.assertFalse((self.root / "escape").exists())

    async def test_mcp_switch_keeps_one_studio_server(self):
        app = self.make_app()
        async with app.run_test(size=(150, 48)) as pilot:
            await pilot.press("enter")
            app.screen.show_section("integrations")
            await pilot.pause(0.3)
            runtime = app.screen.query_one("#mcp-robloxstudio-runtime")
            official = app.screen.query_one("#mcp-Roblox_Studio")
            self.assertTrue(official.value)
            runtime.value = True
            await pilot.pause(0.5)
            self.assertFalse(official.value)
            self.assertTrue(runtime.value)

    async def test_unmanaged_game_is_not_opened(self):
        legacy = self.root / "games" / "Legacy"
        legacy.mkdir()
        (legacy / "default.project.json").write_text("{}", encoding="utf-8")
        app = self.make_app()
        launched = []
        app.run_interactive = lambda *a, **k: launched.append(a)  # must never be reached
        async with app.run_test(size=(150, 48)) as pilot:
            await pilot.press("enter")
            app.screen.show_section("projects")
            await pilot.pause(0.3)
            app.screen.query_one("#pj-table").focus()
            await pilot.press("enter")
            await pilot.pause(0.3)
            self.assertEqual(launched, [])
            await app.workers.wait_for_complete()

    async def test_update_all_runs_every_step_and_shows_a_summary(self):
        from contextlib import ExitStack

        from tests.test_update_all import FakeProcs
        fake = FakeProcs()
        app = self.make_app()
        app.run_interactive = lambda cmd, cwd, **kw: fake.terminal(cmd, cwd)  # the skills step, in the terminal
        with ExitStack() as stack:
            fake.patch(stack)
            async with app.run_test(size=(150, 48)) as pilot:
                await pilot.press("enter")
                app.screen.show_section("settings")
                await pilot.pause()
                app.screen.query_one("#st-update-all").press()
                await pilot.pause()
                await pilot.press("y")  # confirm
                for _ in range(2):  # RoNavi, then (after the skills step) plugins, guards and toolchain
                    await self.wait_for(pilot, lambda: isinstance(app.screen, TaskScreen) and app.screen.done)
                    await pilot.press("escape")
                    await pilot.pause()
                await self.wait_for(pilot, lambda: isinstance(app.screen, TextScreen))
                text = app.screen.text
                self.assertIn("✘ RoNavi", text)  # no origin in the test studio
                self.assertIn("✔ Skills de terceros", text)
                self.assertIn("✔ Plugins de Claude Code", text)
                self.assertIn("✔ Guardianes de los juegos", text)
                self.assertIn("… Toolchain de los juegos", text)
                self.assertEqual(len(fake.interactive), 1)
                await app.workers.wait_for_complete()

    async def test_small_terminal_renders(self):
        app = self.make_app()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("enter")
            await pilot.pause()
            self.assertIsInstance(app.screen, MainScreen)

    async def test_task_close_button_fits_a_short_terminal(self):
        # Regression: the log had a fixed height and pushed "Cerrar" out of the dialog at 120x30.
        from ronavi.ui.modals import Job
        app = self.make_app()
        for size in [(120, 30), (100, 24)]:
            async with app.run_test(size=size) as pilot:
                await pilot.press("enter")
                app.push_screen(TaskScreen("Skills y plugins", [Job("paso", func=lambda log: log("ok"))]))
                await self.wait_for(pilot, lambda: isinstance(app.screen, TaskScreen) and app.screen.done)
                await pilot.pause()
                dialog = app.screen.query_one(".dialog").content_region
                button = app.screen.query_one("#close").region
                self.assertTrue(dialog.contains_region(button), (size, dialog, button))
            app = self.make_app()


class MascotTests(unittest.TestCase):
    @unittest.skipIf(textual is None, "needs rich")
    def test_frames_have_the_same_shape(self):
        for size in ("big", "mini"):
            shapes = {mood: (len(mascot.fox(size, mood).plain.splitlines()),
                             max(map(len, mascot.fox(size, mood).plain.splitlines())))
                      for mood in ("normal", "blink", "wink")}
            self.assertEqual(len(set(shapes.values())), 1, shapes)
        self.assertEqual(len(mascot.fox("big").plain.splitlines()), 14)


if __name__ == "__main__":
    unittest.main()
