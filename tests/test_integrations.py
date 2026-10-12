import json
import unittest

from ronavi.core import integrations
from ronavi.core.environment import EnvCheck, counts, run_doctor, setup_steps
from ronavi.core.skills import inventory
from tests.helpers import StudioTestCase


class McpTests(StudioTestCase):
    def test_one_studio_server_at_a_time(self):
        before = self.tree_hash(self.root, skip=("games", ".claude/settings.local.json"))
        self.assertTrue(integrations.mcp_state(self.root)["Roblox_Studio"])
        integrations.set_mcp(self.root, "robloxstudio-runtime", True)
        state = integrations.mcp_state(self.root)
        self.assertTrue(state["robloxstudio-runtime"])
        self.assertFalse(state["Roblox_Studio"])
        integrations.set_mcp(self.root, "Roblox_Studio", True)
        state = integrations.mcp_state(self.root)
        self.assertTrue(state["Roblox_Studio"])
        self.assertFalse(state["robloxstudio-runtime"])
        # Only the untracked local file changes.
        local = json.loads((self.root / ".claude/settings.local.json").read_text(encoding="utf-8"))
        self.assertIn("robloxstudio-runtime", local["disabledMcpjsonServers"])
        self.assertEqual(self.tree_hash(self.root, skip=("games", ".claude/settings.local.json")), before)

    def test_unknown_names_are_refused(self):
        with self.assertRaises(ValueError):
            integrations.set_mcp(self.root, "evil", True)
        with self.assertRaises(ValueError):
            integrations.set_user_env("PATH", "x")


class EnvironmentTests(StudioTestCase):
    def test_setup_steps_reuse_studio_scripts(self):
        steps = {s.key: s for s in setup_steps(self.studio)}
        self.assertIn("skills", steps)
        flat = [" ".join(c) for c in steps["skills"].commands]
        self.assertTrue(all("skills_sync.py" in c for c in flat))
        self.assertTrue(any(c.endswith(" plugins") for c in flat))
        self.assertIn("requirements.txt", " ".join(steps["pydeps"].commands[0]))

    def test_doctor_runs_as_a_library(self):
        # Regression: doctor.py uses @dataclass, which needs its module in sys.modules.
        checks = run_doctor(self.studio, ["Variables", "Juegos"])
        self.assertTrue(checks)
        self.assertEqual({c.group for c in checks}, {"Variables", "Juegos"})
        self.assertTrue(all(c.status in ("ok", "warn", "fail") for c in checks))

    def test_counts(self):
        checks = [EnvCheck("g", "a", "ok", ""), EnvCheck("g", "b", "warn", ""), EnvCheck("g", "c", "fail", "")]
        self.assertEqual(counts(checks), (1, 1, 1))

    def test_skill_inventory_reads_the_lock(self):
        names = {s.name for s in inventory(self.studio)}
        self.assertTrue({"quota-guard", "studio-doctor", "own-audio", "create-roblox-game",
                         "figma-to-roblox-ui", "roblox-skills@roblox-skills"} <= names)


if __name__ == "__main__":
    unittest.main()
