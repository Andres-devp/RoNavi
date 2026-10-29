import contextlib
import io
import os
import subprocess
import sys
from pathlib import Path

from ronavi import __version__, bootstrap
from ronavi.cli import main
from tests.helpers import REPO, StudioTestCase


class CliTests(StudioTestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_new_list_and_sync(self):
        code, out, _ = self.run_cli("new", "Coin Dash", "--genre", "obby", "--desc", "monedas")
        self.assertEqual(code, 0)
        self.assertTrue((self.root / "games" / "CoinDash" / ".ronavi" / "project.json").exists())
        code, out, _ = self.run_cli("list")
        self.assertEqual(code, 0)
        self.assertIn("CoinDash", out)
        self.assertIn("guardián: sí", out)
        self.assertEqual(self.run_cli("sync-guards")[0], 0)

    def test_ideas_from_the_command_line(self):
        code, out, _ = self.run_cli("idea", "--hint", "algo con zombies", "--no-open")
        self.assertEqual(code, 0)
        idea_root = self.root / "work" / "ideas" / out.strip().splitlines()[-1].split("\\")[-1].split("/")[-1]
        self.assertTrue((idea_root / ".ronavi" / "idea.json").is_file())
        (idea_root / "IDEA.md").write_text("# Zombie Run\n", encoding="utf-8")
        code, out, _ = self.run_cli("ideas")
        self.assertEqual(code, 0)
        self.assertIn("Zombie Run", out)
        code, _, _ = self.run_cli("new", "Zombie Run", "--genre", "obby", "--no-git", "--from-idea", idea_root.name)
        self.assertEqual(code, 0)
        self.assertTrue((self.root / "games" / "ZombieRun" / "docs" / "research" / "IDEA.md").is_file())
        code, _, err = self.run_cli("new", "Other", "--from-idea", "nope")
        self.assertEqual(code, 1)
        self.assertIn("No existe la idea", err)

    def test_launcher_ignores_a_ronavi_package_in_the_current_folder(self):
        # Regression: run from inside another clone, `python -m ronavi` imported that clone's code.
        decoy = self.tmp / "elsewhere" / "ronavi"
        decoy.mkdir(parents=True)
        (decoy / "__init__.py").write_text("", encoding="utf-8")
        (decoy / "__main__.py").write_text("print('decoy')\n", encoding="utf-8")
        cmd = bootstrap.ronavi_command(Path(sys.executable), ["--version"])
        env = dict(os.environ, PYTHONPATH=str(REPO))
        out = subprocess.run(cmd, cwd=decoy.parent, env=env, capture_output=True, text=True,
                             encoding="utf-8").stdout
        self.assertNotIn("decoy", out)
        self.assertIn(__version__, out)

    def test_update_all_reports_every_step(self):
        from contextlib import ExitStack
        from unittest import mock

        from tests.test_update_all import FakeProcs
        fake = FakeProcs()
        with ExitStack() as stack:
            fake.patch(stack)
            stack.enter_context(mock.patch("ronavi.core.launcher.run_here", fake.terminal))
            code, out, _ = self.run_cli("update", "--all")
        self.assertEqual(code, 1)  # the test studio has no origin: RoNavi ✘, the rest still ran
        summary = out.split("Resumen:", 1)[1]
        self.assertIn("✘ RoNavi", summary)
        self.assertIn("✔ Skills de terceros", summary)
        self.assertIn("✔ Plugins de Claude Code", summary)
        self.assertIn("✔ Guardianes de los juegos", summary)
        self.assertIn("… Toolchain de los juegos", summary)
        self.assertEqual(len(fake.interactive), 1)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            main(["update", "--all", "--check"])

    def test_version(self):
        code, out, _ = self.run_cli("--version")
        self.assertEqual(code, 0)
        self.assertIn(__version__, out)

    def test_bad_names_fail_cleanly(self):
        code, _, err = self.run_cli("new", "../../evil")
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        code, _, err = self.run_cli("open", "DoesNotExist")
        self.assertEqual(code, 1)
        self.assertIn("No existe", err)
