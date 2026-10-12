"""Drive the real TUI headless with Textual's pilot. Skipped when Textual is not installed."""

import asyncio
import unittest

try:
    import textual  # noqa: F401
except ImportError:  # the core tests still run without the venv
    textual = None

from tests.helpers import StudioTestCase

if textual:
    from textual.widgets import Checkbox, ContentSwitcher, Input

    from ronavi.ui import mascot
    from ronavi.ui.app import RoNaviApp
    from ronavi.ui.main import MainScreen
    from ronavi.ui.modals import TaskScreen
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
            for key, section in zip("1234567", ["home", "projects", "new", "skills", "tools", "integrations",
                                                 "settings"]):
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

    async def test_small_terminal_renders(self):
        app = self.make_app()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("enter")
            await pilot.pause()
            self.assertIsInstance(app.screen, MainScreen)


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
