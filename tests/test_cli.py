import contextlib
import io

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

    def test_bad_names_fail_cleanly(self):
        code, _, err = self.run_cli("new", "../../evil")
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        code, _, err = self.run_cli("open", "DoesNotExist")
        self.assertEqual(code, 1)
        self.assertIn("No existe", err)
