"""`ronavi update`, the update check and the release notes, against throwaway git repos (no network)."""

import importlib.util
import unittest
from pathlib import Path

from ronavi import __version__
from ronavi.core import updates
from ronavi.core.paths import Studio
from tests.helpers import StudioTestCase, git

RELEASE_NOTES = Path(__file__).resolve().parents[1] / "scripts" / "release_notes.py"


class VersionTests(unittest.TestCase):
    def test_parse_and_pick_the_newest_tag(self):
        self.assertEqual(updates.parse_version("v1.2.3"), (1, 2, 3))
        self.assertIsNone(updates.parse_version("v1.2"))
        self.assertEqual(updates.latest_tag(["v0.2.0", "v0.10.0", "v0.9.1", "nightly", "1.0.0"]), "v0.10.0")
        self.assertIsNone(updates.latest_tag(["nightly"]))

    def test_this_version_has_release_notes(self):
        spec = importlib.util.spec_from_file_location("release_notes_under_test", RELEASE_NOTES)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.ronavi_version(), __version__)
        changelog = (RELEASE_NOTES.parents[1] / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertTrue(mod.notes(changelog, __version__))
        self.assertEqual(mod.notes("## [1.0.0] - x\n\nuno\n\n## [0.9.0]\n\ndos\n", "1.0.0"), "uno")
        self.assertIsNone(mod.notes("## [1.0.0]\nuno\n", "2.0.0"))


class UpdateTests(StudioTestCase):
    """origin (a normal repo with tags) and clones of it standing in for installed studios."""

    def setUp(self):
        super().setUp()
        self.origin = self.tmp / "origin"
        self.origin.mkdir()
        git("init", "-q", "-b", "main", cwd=self.origin)
        self.commit("v0.1.0")
        git("tag", "v0.1.0", cwd=self.origin)

    def commit(self, text: str) -> None:
        (self.origin / "skills.lock.json").write_text('{"v": "%s"}\n' % text, encoding="utf-8")
        git("add", "-A", cwd=self.origin)
        git("commit", "-q", "-m", text, cwd=self.origin)

    def clone(self, name: str, ref: str | None = None) -> Studio:
        target = self.tmp / name
        git("clone", "-q", str(self.origin), str(target), cwd=self.tmp)
        if ref:
            git("-c", "advice.detachedHead=false", "checkout", "-q", ref, cwd=target)
        return Studio.load(target)

    def head(self, studio: Studio) -> str:
        return updates.describe(studio.root)

    def test_installed_studio_moves_to_the_newest_tag(self):
        studio = self.clone("installed", "v0.1.0")
        self.commit("v0.2.0")
        git("tag", "v0.2.0", cwd=self.origin)
        self.commit("unreleased work")  # main moves on; an install stays on releases
        msg = updates.update(studio)
        self.assertEqual(self.head(studio), "v0.2.0")
        self.assertIsNone(updates.current_branch(studio.root))
        self.assertIn("skills", msg)  # skills.lock.json changed between the versions
        self.assertIn("Ya estabas al día", updates.update(studio))

    def test_development_clone_pulls_its_branch(self):
        studio = self.clone("dev")
        self.commit("new feature")
        updates.update(studio)
        self.assertEqual(updates.current_branch(studio.root), "main")
        log = git("log", "-1", "--format=%s", cwd=studio.root).stdout.strip()
        self.assertEqual(log, "new feature")

    def test_local_changes_block_the_update(self):
        studio = self.clone("dirty", "v0.1.0")
        (studio.root / "skills.lock.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaises(updates.UpdateError):
            updates.update(studio)
        self.assertEqual((studio.root / "skills.lock.json").read_text(encoding="utf-8"), "{}\n")

    def test_a_folder_that_is_not_its_own_repo_is_refused(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        with self.assertRaises(updates.UpdateError):
            updates.update(Studio.load(plain))
        inner = self.root / "work" / "inner"  # inside the test studio's git: not its own repo
        inner.mkdir()
        with self.assertRaises(updates.UpdateError):
            updates.update(Studio.load(inner))

    def test_update_check_is_throttled_and_compares_with_this_version(self):
        studio = self.clone("check", "v0.1.0")
        self.assertIsNone(updates.check_for_update(studio, force=True))  # v0.1.0 is not newer
        git("tag", "v99.0.0", cwd=self.origin)
        self.assertIsNone(updates.check_for_update(studio))  # checked a moment ago
        self.assertEqual(updates.check_for_update(studio, force=True), "v99.0.0")
        self.assertGreater(Studio.load(studio.root).config.last_update_check, 0)


if __name__ == "__main__":
    unittest.main()
