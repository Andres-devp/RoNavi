"""Ideas: research without a game, their guard, and turning one into a game."""

import importlib.util
import json
import unittest
from datetime import datetime
from pathlib import Path

from ronavi.core import ideas
from ronavi.core import templates as T
from ronavi.core.guard import GuardError
from ronavi.core.projects import GUARD_CONFIG_REL, GUARD_REL, RESEARCH_REL, create_game, discover
from tests.helpers import StudioTestCase

ASSET = Path(__file__).resolve().parents[1] / "ronavi" / "assets" / "ronavi_guard.py"


def load_guard_module():
    spec = importlib.util.spec_from_file_location("ronavi_guard_for_ideas", ASSET)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class IdeaTests(StudioTestCase):
    def test_creates_an_idea_without_git_or_game(self):
        before = self.template_hash()
        idea = ideas.create_idea(self.studio, "algo   con zombies")
        self.assertEqual(idea.root.parent, self.root / "work" / "ideas")
        self.assertEqual(idea.hint, "algo con zombies")
        for rel in (ideas.IDEA_META, "CLAUDE.md", ".claude/settings.json", ".claude/settings.local.json",
                    GUARD_REL, GUARD_CONFIG_REL):
            self.assertTrue((idea.root / rel).is_file(), rel)
        self.assertFalse((idea.root / ".git").exists())
        self.assertFalse((idea.root / "default.project.json").exists())
        self.assertEqual(discover(self.studio), [])  # an idea is not a game
        self.assertEqual(self.template_hash(), before)
        self.assertIn("algo con zombies", (idea.root / "CLAUDE.md").read_text(encoding="utf-8"))

        cfg = json.loads((idea.root / GUARD_CONFIG_REL).read_text(encoding="utf-8"))
        self.assertEqual(Path(cfg["game_root"]), idea.root)
        self.assertEqual(cfg["allowed"], [str(self.root / "work" / "quota-ledger.json")])

    def test_ids_never_collide_and_listing_is_newest_first(self):
        home = self.studio.ideas_home
        home.mkdir(parents=True)
        now = datetime(2026, 10, 29, 15, 30)
        self.assertEqual(ideas.new_idea_id(home, now), "2026-10-29-1530")
        (home / "2026-10-29-1530").mkdir()
        (home / "2026-10-29-1530-2").mkdir()
        self.assertEqual(ideas.new_idea_id(home, now), "2026-10-29-1530-3")

        first = ideas.create_idea(self.studio)
        second = ideas.create_idea(self.studio)
        self.assertNotEqual(first.id, second.id)
        listed = [i.id for i in ideas.discover_ideas(self.studio)]
        self.assertEqual(listed, sorted(listed, reverse=True))  # plain folders without idea.json are skipped
        self.assertEqual(set(listed), {first.id, second.id})
        self.assertEqual(ideas.find_idea(self.studio, first.id.upper()).root, first.root)
        with self.assertRaises(GuardError):
            ideas.find_idea(self.studio, "nope")

    def test_title_comes_from_idea_md(self):
        idea = ideas.create_idea(self.studio, "pista")
        self.assertEqual(idea.title, "pista")
        (idea.root / "IDEA.md").write_text("intro\n# Zombie Tycoon\n## Concepto 1\n", encoding="utf-8")
        self.assertEqual(ideas.load_idea(self.studio, idea.root).title, "Zombie Tycoon")

    def test_guard_keeps_claude_inside_the_idea(self):
        game = create_game(self.studio, "Alpha").root
        idea = ideas.create_idea(self.studio)
        other = ideas.create_idea(self.studio)
        mod = load_guard_module()
        guard = mod.Guard(json.loads((idea.root / GUARD_CONFIG_REL).read_text(encoding="utf-8")))

        def decide(tool, **tool_input):
            return mod.decide({"tool_name": tool, "tool_input": tool_input, "cwd": str(idea.root)}, guard)

        self.assertIsNone(decide("Write", file_path=str(idea.root / "IDEA.md")))
        self.assertIsNone(decide("Write", file_path="research/market.md"))
        self.assertIsNone(decide("Write", file_path=str(self.root / "work" / "quota-ledger.json")))
        self.assertIsNotNone(decide("Write", file_path=str(other.root / "IDEA.md")))
        self.assertIsNotNone(decide("Write", file_path=str(game / "src" / "x.luau")))
        self.assertIsNotNone(decide("Write", file_path=str(self.root / "games" / "NewGame" / "README.md")))
        self.assertIsNotNone(decide("Edit", file_path=str(self.root / "README.md")))
        self.assertIsNotNone(decide("Bash", command=f'mkdir "{self.root / "games" / "Sneaky"}"'))

    def test_scope_refuses_paths_outside_the_ideas_folder(self):
        with self.assertRaises(GuardError):
            ideas.scope_for_idea(self.studio, self.root / "work" / "elsewhere")
        with self.assertRaises(GuardError):
            ideas.scope_for_idea(self.studio, self.root / "games" / "Alpha")
        with self.assertRaises(GuardError):
            ideas.load_idea(self.studio, self.root / "games")


class IdeaToGameTests(StudioTestCase):
    def test_game_from_idea_gets_the_research(self):
        idea = ideas.create_idea(self.studio, "zombies")
        (idea.root / "IDEA.md").write_text("# Zombie Tycoon\n", encoding="utf-8")
        (idea.root / "research").mkdir()
        (idea.root / "research" / "market.md").write_text("fuentes\n", encoding="utf-8")
        (idea.root / ".scratch").mkdir()
        (idea.root / ".scratch" / "tmp.txt").write_text("x", encoding="utf-8")

        game = create_game(self.studio, "Zombie Tycoon", "tycoon", from_idea=idea.root)
        research = game.root / RESEARCH_REL
        copied = sorted(p.relative_to(research).as_posix() for p in research.rglob("*") if p.is_file())
        self.assertEqual(copied, ["IDEA.md", "research/market.md"])  # no CLAUDE.md, .claude/, .ronavi/, hidden
        self.assertEqual(game.extra["from_idea"], idea.id)
        self.assertEqual(ideas.load_idea(self.studio, idea.root).converted_to, "ZombieTycoon")
        self.assertTrue(idea.root.is_dir())  # the idea is kept

    def test_bad_idea_is_refused_before_anything_is_written(self):
        with self.assertRaises(GuardError):
            create_game(self.studio, "Ghost", "other", from_idea=self.root / "work")
        self.assertFalse((self.root / "games" / "Ghost").exists())


class PromptTests(unittest.TestCase):
    def test_idea_prompt(self):
        blank = T.idea_prompt()
        self.assertIn("IDEA.md", blank)
        self.assertIn("Do NOT create a game folder", blank)
        hinted = T.idea_prompt('zombies & "tycoon" | 100%')
        self.assertIn("zombies", hinted)
        self.assertFalse(set('"%^&|<>`$!') & set(hinted))

    def test_first_prompt_mentions_research_only_when_there_is_some(self):
        self.assertNotIn("docs/research", T.first_prompt("Coin Dash", "CoinDash", "obby", ""))
        self.assertIn("docs/research", T.first_prompt("Coin Dash", "CoinDash", "obby", "", has_research=True))


if __name__ == "__main__":
    unittest.main()
