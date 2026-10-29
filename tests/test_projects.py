import json
import unittest

from ronavi.core import lsp
from ronavi.core import templates as T
from ronavi.core.guard import GuardError
from ronavi.core.projects import (GUARD_CONFIG_REL, GUARD_REL, LUAU_CHECK_REL, adopt_game, create_game, discover,
                                  find_game, load_game, local_settings, posix_rule_path, protected_deny_rules,
                                  refreshed_mcp, sync_all_guards)
from tests.helpers import StudioTestCase, git

MANAGED_GUARD_FILES = (".claude/settings.local.json", GUARD_CONFIG_REL)


class CreateGameTests(StudioTestCase):
    def test_creates_an_independent_project(self):
        game = create_game(self.studio, "Coin Dash", "obby", "Monedas y lava")
        root = self.root / "games" / "CoinDash"
        self.assertEqual(game.root, root)
        for rel in (".ronavi/project.json", "CLAUDE.md", "README.md", ".gitignore", ".mcp.json",
                    ".claude/settings.json", ".claude/settings.local.json", GUARD_REL, GUARD_CONFIG_REL):
            self.assertTrue((root / rel).is_file(), rel)

        meta = json.loads((root / ".ronavi/project.json").read_text(encoding="utf-8"))
        self.assertEqual((meta["name"], meta["genre"], meta["description"]), ("Coin Dash", "obby", "Monedas y lava"))
        self.assertIn(T.BLOCK_BEGIN, (root / "CLAUDE.md").read_text(encoding="utf-8"))

        settings = json.loads((root / ".claude/settings.json").read_text(encoding="utf-8"))
        self.assertIn("Roblox_Studio", settings["enabledMcpjsonServers"])
        self.assertIn("roblox-skills@roblox-skills", settings["enabledPlugins"])
        self.assertIn("Read(.env*)", settings["permissions"]["deny"])
        self.assertFalse(any("scripts/doctor.py" in r for r in settings["permissions"]["allow"]))

        local = json.loads((root / ".claude/settings.local.json").read_text(encoding="utf-8"))
        hook = local["hooks"]["PreToolUse"][0]
        self.assertIn("Bash", hook["matcher"])
        self.assertTrue(hook["hooks"][0]["args"][0].endswith("ronavi_guard.py"))
        self.assertIn(f"Edit({posix_rule_path(self.root / 'README.md')})", local["permissions"]["deny"])

        gitignore = (root / ".gitignore").read_text(encoding="utf-8")
        for line in (".claude/settings.local.json", ".claude/ronavi-guard.json", "*.rbxl"):
            self.assertIn(line, gitignore.splitlines())

        # Its own repository, one commit, nothing left uncommitted (machine files are ignored).
        top = git("rev-parse", "--show-toplevel", cwd=root).stdout.strip()
        self.assertEqual(top.replace("\\", "/").lower(), str(root).replace("\\", "/").lower())
        self.assertEqual(git("rev-list", "--count", "HEAD", cwd=root).stdout.strip(), "1")
        self.assertEqual(git("status", "--porcelain", cwd=root).stdout.strip(), "")

    def test_template_is_never_modified(self):
        before = self.template_hash()
        studio_head = git("rev-parse", "HEAD", cwd=self.root).stdout
        create_game(self.studio, "Alpha", "tycoon")
        create_game(self.studio, "Beta", "obby")
        self.assertEqual(self.template_hash(), before)
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.root).stdout, studio_head)
        self.assertEqual(git("status", "--porcelain", cwd=self.root).stdout.strip(), "")

    def test_creating_a_game_leaves_other_games_alone(self):
        a = create_game(self.studio, "Alpha", "tycoon")
        (a.root / "src").mkdir()
        (a.root / "src" / "Main.luau").write_text("print('a')\n", encoding="utf-8")
        before = self.tree_hash(a.root, skip=MANAGED_GUARD_FILES)
        a_head = git("rev-parse", "HEAD", cwd=a.root).stdout
        b = create_game(self.studio, "Beta", "obby")
        self.assertEqual(self.tree_hash(a.root, skip=MANAGED_GUARD_FILES), before)
        self.assertEqual(git("rev-parse", "HEAD", cwd=a.root).stdout, a_head)
        # Alpha's guard now also protects Beta (machine-only file, ignored by Alpha's git).
        local = json.loads((a.root / ".claude/settings.local.json").read_text(encoding="utf-8"))
        self.assertIn(f"Edit({posix_rule_path(b.root)}/**)", local["permissions"]["deny"])
        self.assertNotIn(f"Edit({posix_rule_path(a.root)}/**)", local["permissions"]["deny"])

    def test_duplicates_and_bad_input_are_refused(self):
        create_game(self.studio, "Coin Dash")
        with self.assertRaises(GuardError):
            create_game(self.studio, "coin dash")
        with self.assertRaises(GuardError):
            create_game(self.studio, "../Escape")
        with self.assertRaises(GuardError):
            create_game(self.studio, "Valid", genre="not-a-genre")
        self.assertFalse((self.root / "Escape").exists())

    def test_without_git(self):
        game = create_game(self.studio, "No Git", init_git=False)
        self.assertFalse((game.root / ".git").exists())
        self.assertEqual(game.git_summary(), "sin git")


class AdoptAndDiscoverTests(StudioTestCase):
    def test_adopt_keeps_existing_content(self):
        legacy = self.root / "games" / "Legacy"
        legacy.mkdir()
        (legacy / "default.project.json").write_text("{}\n", encoding="utf-8")
        (legacy / "CLAUDE.md").write_text("# Mis notas\nNo borrar.\n", encoding="utf-8")
        (legacy / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
        found = find_game(self.studio, "legacy")
        self.assertFalse(found.managed)

        game = adopt_game(self.studio, found, "horror")
        self.assertTrue(game.managed)
        claude_md = (legacy / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("No borrar.", claude_md)
        self.assertIn(T.BLOCK_BEGIN, claude_md)
        gitignore = (legacy / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertEqual(gitignore[0], "node_modules/")
        self.assertIn("*.rbxl", gitignore)
        self.assertEqual((legacy / "default.project.json").read_text(encoding="utf-8"), "{}\n")

        # Adopting twice changes nothing: the managed block is replaced in place.
        adopt_game(self.studio, load_game(legacy))
        self.assertEqual((legacy / "CLAUDE.md").read_text(encoding="utf-8"), claude_md)

    def test_discover(self):
        create_game(self.studio, "Alpha")
        (self.root / "games" / ".hidden").mkdir()
        (self.root / "games" / "Loose").mkdir()  # no markers: not a game
        names = [g.slug for g in discover(self.studio)]
        self.assertEqual(names, ["Alpha"])


class GuardRulesTests(StudioTestCase):
    def test_deny_rules_cover_template_and_siblings_only(self):
        a = create_game(self.studio, "Alpha")
        b = create_game(self.studio, "Beta")
        rules = protected_deny_rules(self.studio, a.root)
        self.assertIn(f"Edit({posix_rule_path(b.root)}/**)", rules)
        self.assertIn(f"Edit({posix_rule_path(self.root / 'scripts')}/**)", rules)
        self.assertNotIn(f"Edit({posix_rule_path(a.root)}/**)", rules)
        self.assertFalse(any(r.startswith(f"Edit({posix_rule_path(self.root / 'games')}/**") for r in rules))
        self.assertFalse(any(posix_rule_path(self.root / "work") in r for r in rules))
        self.assertTrue(all(r.startswith("Edit(//") for r in rules))

    def test_local_settings_keep_user_rules_and_drop_stale_ones(self):
        a = create_game(self.studio, "Alpha")
        stale = f"Edit({posix_rule_path(self.root / 'games' / 'Deleted')}/**)"
        user = {
            "permissions": {"deny": ["Bash(rm -rf *)", stale], "allow": ["Bash(npm test)"]},
            "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "mine.sh"}]}]},
            "enabledMcpjsonServers": ["blender-ahujasid"],
        }
        data = local_settings(self.studio, a.root, user)
        self.assertIn("Bash(rm -rf *)", data["permissions"]["deny"])
        self.assertNotIn(stale, data["permissions"]["deny"])
        self.assertEqual(data["permissions"]["allow"], ["Bash(npm test)"])
        commands = [h["command"] for e in data["hooks"]["PreToolUse"] for h in e["hooks"]]
        self.assertIn("mine.sh", commands)
        self.assertEqual(sum("ronavi_guard.py" in " ".join(h.get("args", [])) for e in data["hooks"]["PreToolUse"]
                             for h in e["hooks"]), 1)
        self.assertNotIn("blender-ahujasid", data["disabledMcpjsonServers"])  # user's choice kept
        self.assertIn("robloxstudio-runtime", data["disabledMcpjsonServers"])

    def test_sync_all_guards_is_idempotent(self):
        a = create_game(self.studio, "Alpha")
        create_game(self.studio, "Beta")
        first = (a.root / ".claude/settings.local.json").read_text(encoding="utf-8")
        self.assertEqual(sync_all_guards(self.studio), [])
        self.assertEqual((a.root / ".claude/settings.local.json").read_text(encoding="utf-8"), first)
        self.assertEqual(git("status", "--porcelain", cwd=a.root).stdout.strip(), "")


class PostEditAndPluginTests(StudioTestCase):
    def test_games_get_the_luau_check_hook_and_the_lsp_plugin(self):
        game = create_game(self.studio, "Alpha")
        self.assertTrue((game.root / LUAU_CHECK_REL).is_file())
        local = json.loads((game.root / ".claude/settings.local.json").read_text(encoding="utf-8"))
        post = local["hooks"]["PostToolUse"]
        self.assertEqual(len(post), 1)
        self.assertIn("Edit", post[0]["matcher"])
        self.assertTrue(post[0]["hooks"][0]["args"][0].endswith("ronavi_luau_check.py"))
        self.assertTrue(local["enabledPlugins"][lsp.PLUGIN_ID])
        source = local["extraKnownMarketplaces"][lsp.MARKETPLACE]["source"]
        self.assertEqual((source["source"], source["path"]), ("directory", str(lsp.plugins_root(self.studio))))
        self.assertTrue((lsp.plugins_root(self.studio) / lsp.PLUGIN / ".lsp.json").is_file())

    def test_user_hooks_and_a_disabled_plugin_survive_a_sync(self):
        game = create_game(self.studio, "Alpha")
        user = {"hooks": {"PostToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "command": "mine.sh"}]}]},
                "enabledPlugins": {lsp.PLUGIN_ID: False}}
        data = local_settings(self.studio, game.root, local_settings(self.studio, game.root, user))
        commands = [h["command"] for e in data["hooks"]["PostToolUse"] for h in e["hooks"]]
        self.assertIn("mine.sh", commands)
        self.assertEqual(sum("ronavi_luau_check.py" in " ".join(h.get("args", []))
                             for e in data["hooks"]["PostToolUse"] for h in e["hooks"]), 1)
        self.assertFalse(data["enabledPlugins"][lsp.PLUGIN_ID])

    def test_sync_brings_new_studio_rules_and_pins_to_old_games(self):
        game = create_game(self.studio, "Alpha")
        settings_path, mcp_path = game.root / ".claude/settings.json", game.root / ".mcp.json"
        old = json.loads(settings_path.read_text(encoding="utf-8"))
        old["permissions"]["deny"] = ["Read(.env*)", "Bash(my-own-rule)"]
        settings_path.write_text(json.dumps(old), encoding="utf-8")
        mcp = json.loads(mcp_path.read_text(encoding="utf-8"))
        args = mcp["mcpServers"]["robloxstudio-runtime"]["args"]
        args[args.index(next(a for a in args if a.startswith("@chrrxs/")))] = "@chrrxs/robloxstudio-mcp@3.0.0"
        mcp_path.write_text(json.dumps(mcp), encoding="utf-8")

        sync_all_guards(self.studio)
        deny = json.loads(settings_path.read_text(encoding="utf-8"))["permissions"]["deny"]
        self.assertIn("Bash(my-own-rule)", deny)  # the game's own rule stays
        self.assertIn("mcp__robloxstudio-runtime__set_script_source", deny)
        studio_args = json.loads((self.root / ".mcp.json").read_text(encoding="utf-8"))[
            "mcpServers"]["robloxstudio-runtime"]["args"]
        game_args = json.loads(mcp_path.read_text(encoding="utf-8"))["mcpServers"]["robloxstudio-runtime"]["args"]
        self.assertEqual(game_args, studio_args)

    def test_refreshed_mcp_only_touches_pinned_packages(self):
        studio = {"mcpServers": {"rt": {"args": ["/c", "npx", "-y", "@chrrxs/robloxstudio-mcp@9.9.9"]}}}
        game = {"mcpServers": {"rt": {"args": ["/c", "npx", "-y", "@chrrxs/robloxstudio-mcp@1.0.0", "--mine"]},
                               "other": {"command": "x", "args": ["@chrrxs/robloxstudio-mcp@1.0.0"]}}}
        out = refreshed_mcp(studio, game)
        self.assertEqual(out["mcpServers"]["rt"]["args"], ["/c", "npx", "-y", "@chrrxs/robloxstudio-mcp@9.9.9", "--mine"])
        self.assertEqual(out["mcpServers"]["other"]["args"], ["@chrrxs/robloxstudio-mcp@1.0.0"])  # not in the studio
        self.assertEqual(game["mcpServers"]["rt"]["args"][3], "@chrrxs/robloxstudio-mcp@1.0.0")  # input untouched


if __name__ == "__main__":
    unittest.main()
