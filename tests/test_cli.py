import contextlib
import io

from ronavi import __version__
from ronavi.cli import main
from tests.helpers import StudioTestCase


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
