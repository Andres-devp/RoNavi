import os
import unittest

from ronavi.core.guard import (GameScope, GuardError, assert_git_isolated, is_within, same_path, slugify,
                               validate_name)
from tests.helpers import StudioTestCase, git, make_link


class NameTests(unittest.TestCase):
    def test_valid_names(self):
        self.assertEqual(validate_name("Coin Dash"), ("Coin Dash", "CoinDash"))
        self.assertEqual(validate_name("  obby   rush "), ("obby rush", "ObbyRush"))
        self.assertEqual(slugify("tower_defense-2"), "TowerDefense2")

    def test_rejected_names(self):
        for bad in ["", "a", "1Obby", "../Escape", "Obby/Rush", "Juegó", "x" * 41, "C:\\games", "Coin.Dash",
                    "con", "Lpt1", "nul"]:
            with self.subTest(bad=bad), self.assertRaises(GuardError):
                validate_name(bad)


class ScopeTests(StudioTestCase):
    def test_paths_compare_by_component(self):
        home = self.root / "games"
        self.assertTrue(is_within(home / "Foo" / "x.txt", home / "Foo"))
        self.assertFalse(is_within(home / "FooBar", home / "Foo"))
        if os.name == "nt":
            self.assertTrue(same_path(str(home).upper(), str(home).lower()))

    def test_scope_only_for_direct_children_of_games_home(self):
        home = self.root / "games"
        GameScope(home / "Foo", self.root, home)
        for bad in (home, self.root, home / "Foo" / "Nested", self.tmp / "elsewhere"):
            with self.subTest(bad=bad), self.assertRaises(GuardError):
                GameScope(bad, self.root, home)
        with self.assertRaises(GuardError):  # the games home cannot be the studio itself
            GameScope(self.root / "Foo", self.root, self.root)

    def test_writes_cannot_escape(self):
        home = self.root / "games"
        (home / "Foo").mkdir()
        (home / "Other").mkdir()
        scope = GameScope(home / "Foo", self.root, home)
        self.assertTrue(scope.check("src/main.luau").name == "main.luau")
        for bad in ("../Other/x.txt", "..\\Other\\x.txt", str(self.root / "README.md"), "../../CLAUDE.md",
                    str(home / "Other" / "x")):
            with self.subTest(bad=bad), self.assertRaises(GuardError):
                scope.check(bad)
        with self.assertRaises(GuardError):
            scope.write_text("../Other/evil.txt", "x")
        self.assertFalse((home / "Other" / "evil.txt").exists())

    def test_links_inside_the_game_cannot_leave_it(self):
        home = self.root / "games"
        (home / "Foo").mkdir()
        (home / "Other").mkdir()
        make_link(home / "Foo" / "shortcut", home / "Other")
        scope = GameScope(home / "Foo", self.root, home)
        with self.assertRaises(GuardError):
            scope.write_text("shortcut/evil.txt", "x")
        self.assertFalse((home / "Other" / "evil.txt").exists())

    def test_git_must_belong_to_the_game(self):
        game = self.root / "games" / "Foo"
        game.mkdir()
        # The studio is a git repo, so without its own .git the game would use the studio's.
        with self.assertRaises(GuardError):
            assert_git_isolated(game)
        git("init", "-q", cwd=game)
        assert_git_isolated(game)


if __name__ == "__main__":
    unittest.main()
