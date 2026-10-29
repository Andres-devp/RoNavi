"""own-images (Asphalt) and cloud-test (Open Cloud Luau Execution): the parts that need no network."""

import importlib.util
import json
import os
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

SKILLS = Path(__file__).resolve().parents[1] / ".claude" / "skills"


def load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, SKILLS / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


images = load("own_images_under_test", "own-images/scripts/images.py")
cloud = load("cloud_test_under_test", "cloud-test/scripts/cloud_test.py")


def png(path: Path, w: int, h: int) -> None:
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * w for _ in range(h))

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class TempGame(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(os.path.realpath(self._tmp.name)) / "CoinDash"
        self.root.mkdir()

    def tearDown(self):
        self._tmp.cleanup()


class OwnImagesTests(TempGame):
    def test_check_flags_names_formats_and_oversized_pngs(self):
        base = self.root / images.INPUT_DIR
        png(base / "icons" / "coin.png", 4, 4)
        png(base / "Bad Name.png", 4, 4)
        png(base / "huge.png", 2048, 8)
        (base / "music.ogg").write_bytes(b"OggS")
        self.assertEqual(images.problems_for(base / "icons" / "coin.png", self.root), [])
        self.assertTrue(any("lowercase" in i for i in images.problems_for(base / "Bad Name.png", self.root)))
        self.assertTrue(any("1024" in i for i in images.problems_for(base / "huge.png", self.root)))
        self.assertTrue(any("own-audio" in i for i in images.problems_for(base / "music.ogg", self.root)))
        self.assertEqual(images.png_size(base / "huge.png"), (2048, 8))

    def test_generated_config_reads_only_images_and_never_holds_the_key(self):
        text = images.asphalt_toml("group", "123")
        self.assertIn('type = "group"\nid = 123', text)
        self.assertIn(f'path = "{images.INPUT_DIR}/**/*"', text)
        self.assertIn(f'output_path = "{images.OUTPUT_DIR}"', text)
        self.assertNotIn("api", text.lower().replace("# gitignored", ""))

    def test_creator_prefers_the_group_and_explains_when_missing(self):
        with mock.patch.dict(os.environ, {"ROBLOX_GROUP_ID": "7", "ROBLOX_USER_ID": "9"}):
            self.assertEqual(images.creator(), ("group", "7"))
        with mock.patch.dict(os.environ, {"ROBLOX_USER_ID": "9"}, clear=True):
            self.assertEqual(images.creator(), ("user", "9"))
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(SystemExit) as ctx:
            images.creator()
        self.assertIn("setx", str(ctx.exception))

    def test_pending_uploads_parses_the_dry_run(self):
        def fake(code, out):
            return lambda exe, root, *args, env=None: subprocess.CompletedProcess(args, code, out, "")
        with mock.patch.object(images, "asphalt", fake(0, "")):
            self.assertEqual(images.pending_uploads("asphalt", self.root), 0)
        with mock.patch.object(images, "asphalt", fake(1, "Error: Dry run: 2 new assets would be synced")):
            self.assertEqual(images.pending_uploads("asphalt", self.root), 2)
        with mock.patch.object(images, "asphalt", fake(1, "Error: config file not found")), \
                self.assertRaises(SystemExit):
            images.pending_uploads("asphalt", self.root)

    def test_gitignore_gets_the_generated_files_once(self):
        (self.root / ".gitignore").write_text("*.rbxl\n", encoding="utf-8")
        images.ensure_gitignore(self.root)
        images.ensure_gitignore(self.root)
        lines = (self.root / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "*.rbxl")
        self.assertEqual(lines.count("asphalt.toml"), 1)
        self.assertIn(".asphalt-debug/", lines)


class CloudTestProjectTests(TempGame):
    def test_test_project_mirrors_tests_and_shared_with_absolute_paths(self):
        (self.root / "tests").mkdir()
        (self.root / "src" / "shared").mkdir(parents=True)
        (self.root / "default.project.json").write_text(json.dumps({
            "name": "CoinDash",
            "tree": {"$className": "DataModel", "ReplicatedStorage": {"Shared": {"$path": "src/shared"}}}}),
            encoding="utf-8")
        project = cloud.test_project(self.root)
        shared = project["tree"]["ReplicatedStorage"]["Shared"]["$path"]
        self.assertTrue(Path(shared).is_absolute())
        folder = project["tree"]["ServerStorage"][cloud.TEST_FOLDER]
        self.assertEqual(Path(folder["tests"]["$path"]), (self.root / "tests").resolve())
        self.assertEqual(Path(folder["src"]["shared"]["$path"]), (self.root / "src" / "shared").resolve())
        self.assertIn("cloud-test", project["name"])

    def test_counts_specs_in_subfolders(self):
        (self.root / "tests" / "engine").mkdir(parents=True)
        for rel in ("A.spec.luau", "engine/B.spec.luau", "helper.luau"):
            (self.root / "tests" / rel).write_text("return {}\n", encoding="utf-8")
        self.assertEqual(cloud.count_specs(self.root), 2)


class CloudTestTaskTests(unittest.TestCase):
    def test_report_from_a_completed_task(self):
        report = {"passed": 1, "failed": 0, "results": [{"spec": "A.spec", "test": "t", "ok": True}]}
        for output in ({"results": [json.dumps(report)]}, [json.dumps(report)]):
            self.assertEqual(cloud.task_report({"state": "COMPLETE", "output": output}), report)

    def test_failed_or_odd_tasks_become_one_failure(self):
        failed = cloud.task_report({"state": "FAILED", "error": {"message": "Script error"}})
        self.assertEqual(failed["failed"], 1)
        self.assertEqual(failed["results"][0]["err"], "Script error")
        odd = cloud.task_report({"state": "COMPLETE", "output": {"results": ["not json"]}})
        self.assertEqual(odd["failed"], 1)

    def test_wait_task_polls_until_done_with_backoff(self):
        states = iter(["PROCESSING", "COMPLETE"])
        seen, sleeps = [], []

        def fake_request(method, url, api_key, body=None, content_type="application/json"):
            seen.append((method, url))
            return {"path": "universes/1/places/2/versions/3/luau-execution-sessions/s/tasks/t",
                    "state": next(states)}

        with mock.patch.object(cloud, "request", fake_request):
            task = cloud.wait_task({"path": "universes/1/places/2/versions/3/luau-execution-sessions/s/tasks/t",
                                    "state": "QUEUED"}, "key", sleep=sleeps.append, clock=lambda: 0.0)
        self.assertEqual(task["state"], "COMPLETE")
        self.assertEqual(len(seen), 2)
        self.assertTrue(all(u.startswith(cloud.API + "/cloud/v2/universes/1/") for _, u in seen))
        self.assertEqual(sleeps, [2.0, 3.0])

    def test_wait_task_gives_up_after_the_deadline(self):
        ticks = iter([0.0, cloud.POLL_DEADLINE + 1])
        with mock.patch.object(cloud, "request", lambda *a, **k: {"path": "p", "state": "QUEUED"}), \
                self.assertRaises(cloud.CloudError):
            cloud.wait_task({"path": "p", "state": "QUEUED"}, "key", sleep=lambda s: None, clock=lambda: next(ticks))

    def test_publish_saves_not_publishes(self):
        self.assertIn("versionType=Saved", cloud.PUBLISH_URL)
        calls = []

        def fake_request(method, url, api_key, body=None, content_type="application/json"):
            calls.append((url, content_type, body))
            return {"versionNumber": 12}

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(cloud, "request", fake_request):
            place = Path(tmp) / "x.rbxl"
            place.write_bytes(b"<roblox!")
            self.assertEqual(cloud.publish(place, "1", "2", "key"), 12)
        self.assertEqual(calls[0][1], "application/octet-stream")
        self.assertEqual(calls[0][2], b"<roblox!")

    def test_runner_is_shipped_and_strict(self):
        text = cloud.RUNNER.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("--!strict"))
        self.assertIn(cloud.TEST_FOLDER, text)
        self.assertIn("JSONEncode", text)


if __name__ == "__main__":
    unittest.main()
