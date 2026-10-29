import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ronavi.core import toolchain
from ronavi.core.toolchain import PINS, upgraded_text, upgrade_toolchain

SCAFFOLD = """# Coin Dash - pinned toolchain (run `aftman install`)
[tools]
rojo = "rojo-rbx/rojo@7.4.1"
wally = "UpliftGames/wally@0.3.2"
selene = "Kampfkarren/selene@0.28.0"
stylua = "JohnnyMorganz/StyLua@0.20.0"
lune = "lune-org/lune@0.8.9"
"""


class UpgradedTextTests(unittest.TestCase):
    def test_moves_proven_tools_adds_luau_lsp_and_keeps_lune(self):
        text, changes, added = upgraded_text(SCAFFOLD)
        self.assertIn(f'rojo = "rojo-rbx/rojo@{PINS["rojo"][1]}"', text)
        self.assertIn(f'stylua = "JohnnyMorganz/StyLua@{PINS["stylua"][1]}"', text)
        self.assertIn('lune = "lune-org/lune@0.8.9"', text)  # D21: newer Lune breaks the spec runner
        self.assertIn('wally = "UpliftGames/wally@0.3.2"', text)
        self.assertTrue(text.rstrip().endswith(f'luau-lsp = "JohnnyMorganz/luau-lsp@{PINS["luau-lsp"][1]}"'))
        self.assertEqual(added, ["luau-lsp"])
        self.assertEqual(len(changes), 4)
        self.assertTrue(text.startswith("# Coin Dash") and text.endswith("\n"))

    def test_is_idempotent_and_never_downgrades(self):
        once, _, _ = upgraded_text(SCAFFOLD)
        twice, changes, added = upgraded_text(once)
        self.assertEqual((twice, changes, added), (once, [], []))
        newer = SCAFFOLD.replace("rojo-rbx/rojo@7.4.1", "rojo-rbx/rojo@99.0.0")
        text, changes, _ = upgraded_text(newer)
        self.assertIn("rojo-rbx/rojo@99.0.0", text)
        self.assertFalse(any(c.startswith("rojo") for c in changes))

    def test_leaves_other_tables_forks_and_odd_versions_alone(self):
        text = ('[tools]\nrojo = "someone/rojo-fork@7.0.0"\nselene = "Kampfkarren/selene@main"\n\n'
                '[other]\nstylua = "JohnnyMorganz/StyLua@0.1.0"\n')
        new, changes, added = upgraded_text(text)
        self.assertIn('rojo = "someone/rojo-fork@7.0.0"', new)
        self.assertIn('selene = "Kampfkarren/selene@main"', new)
        self.assertIn('[other]\nstylua = "JohnnyMorganz/StyLua@0.1.0"', new)
        self.assertEqual(added, ["luau-lsp"])
        self.assertEqual(changes, [f"luau-lsp {PINS['luau-lsp'][1]} (nuevo)"])
        self.assertLess(new.index("luau-lsp"), new.index("[other]"))  # added inside [tools]

    def test_no_tools_table_means_no_change(self):
        self.assertEqual(upgraded_text("# empty\n"), ("# empty\n", [], []))


class UpgradeToolchainTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_writes_the_manifest_and_trusts_new_tools(self):
        (self.root / "aftman.toml").write_text(SCAFFOLD, encoding="utf-8")
        lines, trusted = [], []
        with mock.patch.object(toolchain, "trust", lambda repo: trusted.append(repo) or True):
            changes = upgrade_toolchain(self.root, lines.append)
            self.assertEqual(upgrade_toolchain(self.root, lines.append), [])
        self.assertEqual(len(changes), 4)
        self.assertEqual(trusted, [PINS["luau-lsp"][0]])
        self.assertIn("luau-lsp", (self.root / "aftman.toml").read_text(encoding="utf-8"))
        self.assertTrue(any("check.py --fix" in line for line in lines))

    def test_rokit_manifest_wins_and_no_manifest_is_fine(self):
        self.assertEqual(upgrade_toolchain(self.root), [])
        (self.root / "rokit.toml").write_text('[tools]\nrojo = "rojo-rbx/rojo@7.0.0"\n', encoding="utf-8")
        (self.root / "aftman.toml").write_text(SCAFFOLD, encoding="utf-8")
        with mock.patch.object(toolchain, "trust", lambda repo: False):
            lines = []
            upgrade_toolchain(self.root, lines.append)
        self.assertIn(PINS["rojo"][1], (self.root / "rokit.toml").read_text(encoding="utf-8"))
        self.assertEqual((self.root / "aftman.toml").read_text(encoding="utf-8"), SCAFFOLD)
        self.assertTrue(any("rokit trust" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
