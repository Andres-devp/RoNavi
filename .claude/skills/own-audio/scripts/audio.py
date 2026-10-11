#!/usr/bin/env python3
"""Own audio pipeline: WAV from your DAW -> normalised OGG -> Open Cloud -> SoundBank.

    python audio.py check  --game CoinDash               # names, format, limits (no ffmpeg needed)
    python audio.py build  --game CoinDash               # normalise + convert with ffmpeg
    python audio.py upload --game CoinDash               # dry run: what would upload
    python audio.py upload --game CoinDash --yes         # upload (after quota-guard approval)
    python audio.py bank   --game CoinDash [--merge work/manifest.json]

Layout inside the game (games/<Game>/assets/audio/):
    source/<category>_<name>_<variant>.wav   your masters (input)
    build/<stem>.ogg                          converted files (output of build)
    audio.lock.json                           hashes, durations and asset ids (commit it)
    bank/SoundBank.luau, bank/Sfx.luau        output of bank (copy to src/shared/...)

The SoundBank uses the exact Entry shape that SyphoDev's roblox-sfx emits, and Sfx.luau
is taken from its emit_bank.py at run time, so both banks are interchangeable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
QUOTA = REPO / ".claude" / "skills" / "quota-guard" / "scripts" / "quota.py"
SFX_EMITTER = Path.home() / ".claude" / "skills" / "roblox-sfx" / "scripts"

ASSETS_URL = "https://apis.roblox.com/assets/v1/assets"
OPERATION_URL = "https://apis.roblox.com/assets/v1/operations/{op}"

# Roblox limits for audio assets, checked 2026-10-11 (see docs/quotas.md).
MAX_SECONDS = 7 * 60
MAX_BYTES = 20 * 1024 * 1024
MAX_RATE = 48000

NAME_RE = re.compile(r"^(?P<category>[a-z0-9]+)_(?P<name>[a-z0-9-]+)_(?P<variant>[a-z0-9-]+)$")

# House conventions (not Roblox rules): channel layout and loudness per category.
# Positional 3D effects must be mono so Roblox can pan them; music, ambience and UI
# are heard "in the head" and keep stereo.
STEREO = {"music", "amb", "ui"}
LOOPED = {"music", "amb"}
TARGETS = {  # integrated LUFS for long material; short sounds are peak-normalised
    "music": -16.0,
    "amb": -20.0,
}
PEAK_DBFS = -1.0     # sample-peak target for short sounds; true-peak ceiling for loudnorm
DEFAULT_VOLUME = {"music": 0.3, "amb": 0.2, "ui": 0.5}
BUILD_PARAMS_VERSION = 1  # bump when the conversion recipe changes, to force a rebuild


# --------------------------------------------------------------------------- paths and state

def games_home() -> Path:
    env = os.environ.get("ROBLOX_GAMES_HOME")
    return Path(env).expanduser() if env else REPO / "games"


def audio_dir(game: str) -> Path:
    root = Path(game) if Path(game).is_dir() else games_home() / game
    if not root.is_dir():
        raise SystemExit(f"game folder not found: {root} (set ROBLOX_GAMES_HOME or pass a path)")
    return root / "assets" / "audio"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_lock(ad: Path) -> dict:
    p = ad / "audio.lock.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"version": 1, "sounds": {}}


def save_lock(ad: Path, lock: dict) -> None:
    (ad / "audio.lock.json").write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8",
                                        newline="\n")


def sources(ad: Path) -> list[Path]:
    src = ad / "source"
    if not src.is_dir():
        raise SystemExit(f"no source folder: {src}  (put your WAV masters there)")
    return sorted(p for p in src.iterdir() if p.is_file() and not p.name.startswith("."))


def recipe(category: str) -> dict:
    return {"v": BUILD_PARAMS_VERSION, "channels": 2 if category in STEREO else 1, "rate": MAX_RATE,
            "lufs": TARGETS.get(category), "peak": PEAK_DBFS, "codec": "libvorbis-q6"}


def recipe_key(source_hash: str, category: str) -> str:
    return hashlib.sha256((source_hash + json.dumps(recipe(category), sort_keys=True)).encode()).hexdigest()


# --------------------------------------------------------------------------- check

def wav_info(path: Path) -> dict:
    with wave.open(str(path), "rb") as w:
        frames, rate = w.getnframes(), w.getframerate()
        return {"channels": w.getnchannels(), "rate": rate, "bits": 8 * w.getsampwidth(),
                "seconds": frames / float(rate)}


def cmd_check(a) -> int:
    ad = audio_dir(a.game)
    problems = 0
    for p in sources(ad):
        issues = []
        m = NAME_RE.match(p.stem)
        if p.suffix.lower() != ".wav":
            issues.append("not a .wav master")
        if not m:
            issues.append("name must be <category>_<name>_<variant>, lowercase, e.g. sfx_coin-pickup_01")
        info = None
        if p.suffix.lower() == ".wav":
            try:
                info = wav_info(p)
            except (wave.Error, EOFError) as exc:
                issues.append(f"unreadable WAV ({exc}); 32-bit float WAVs need ffmpeg: run build")
        if info:
            if info["seconds"] > MAX_SECONDS:
                issues.append(f"{info['seconds']:.0f}s > Roblox limit of {MAX_SECONDS}s")
            if m and m["category"] not in STEREO and info["channels"] > 1:
                issues.append("stereo master for a 3D effect: build will fold it to mono (check the mix)")
        desc = (f"{info['channels']}ch {info['rate']}Hz {info['bits']}bit {info['seconds']:.2f}s" if info else "")
        mark = "ok " if not issues else "!! "
        problems += bool(issues)
        print(f"{mark}{p.name:40} {desc}")
        for i in issues:
            print(f"     - {i}")
    print(f"\n{problems} file(s) with issues")
    return 1 if problems else 0


# --------------------------------------------------------------------------- build

def need_ffmpeg() -> tuple[str, str]:
    ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ff and fp:
        return ff, fp
    print("ffmpeg/ffprobe not found. Install it, open a new terminal and retry:")
    print("  Windows: winget install Gyan.FFmpeg")
    print("  macOS:   brew install ffmpeg")
    print("  Linux:   sudo apt install ffmpeg   (or your distro's package)")
    raise SystemExit(3)


def probe(ffprobe: str, path: Path) -> dict:
    out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration:stream=channels,sample_rate",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    st = data["streams"][0]
    return {"seconds": float(data["format"]["duration"]), "channels": int(st["channels"]),
            "rate": int(st["sample_rate"])}


def measure_peak(ffmpeg: str, path: Path, channels: int) -> float:
    res = subprocess.run([ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-ac", str(channels),
                          "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"max_volume:\s*(-?[\d.]+) dB", res.stderr)
    return float(m.group(1)) if m else 0.0


def loudnorm_filter(ffmpeg: str, path: Path, lufs: float, channels: int) -> str:
    """Two-pass EBU R128 loudnorm: measure, then apply linearly with the measured values."""
    base = f"loudnorm=I={lufs}:TP={PEAK_DBFS}:LRA=11"
    res = subprocess.run([ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-ac", str(channels),
                          "-af", base + ":print_format=json", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", res.stderr, re.S)
    if not m:
        return base
    j = json.loads(m.group(0))
    return (f"{base}:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
            f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")


def cmd_build(a) -> int:
    ffmpeg, ffprobe = need_ffmpeg()
    ad = audio_dir(a.game)
    out_dir = ad / "build"
    out_dir.mkdir(parents=True, exist_ok=True)
    lock = load_lock(ad)
    built = skipped = 0
    for p in sources(ad):
        m = NAME_RE.match(p.stem)
        if not m or p.suffix.lower() != ".wav":
            print(f"skip   {p.name} (fails check; run: audio.py check)")
            continue
        cat = m["category"]
        src_hash = sha256(p)
        key = recipe_key(src_hash, cat)
        out = out_dir / f"{p.stem}.ogg"
        entry = lock["sounds"].get(p.stem, {})
        if not a.force and entry.get("build_key") == key and out.exists():
            skipped += 1
            continue
        r = recipe(cat)
        if r["lufs"] is not None and probe(ffprobe, p)["seconds"] >= 3.0:
            af = loudnorm_filter(ffmpeg, p, r["lufs"], r["channels"])
            mode = f"{r['lufs']} LUFS"
        else:  # short sounds: loudness integration is meaningless, normalise the peak
            gain = PEAK_DBFS - measure_peak(ffmpeg, p, r["channels"])
            af = f"volume={gain:.2f}dB"
            mode = f"peak {PEAK_DBFS} dBFS"
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(p), "-ac", str(r["channels"]),
                        "-af", af, "-ar", str(r["rate"]), "-c:a", "libvorbis", "-q:a", "6", str(out)], check=True)
        info = probe(ffprobe, out)
        size = out.stat().st_size
        if info["seconds"] > MAX_SECONDS or size > MAX_BYTES:
            raise SystemExit(f"{out.name}: {info['seconds']:.0f}s / {size / 1e6:.1f} MB exceeds Roblox limits")
        entry.update({"source": f"source/{p.name}", "source_sha256": src_hash, "build_key": key,
                      "build": f"build/{out.name}", "build_sha256": sha256(out), "category": cat,
                      "seconds": round(info["seconds"], 3), "channels": info["channels"], "rate": info["rate"],
                      "bytes": size})
        lock["sounds"][p.stem] = entry
        built += 1
        print(f"built  {out.name:40} {info['channels']}ch {info['seconds']:.2f}s {size / 1024:.0f} KB ({mode})")
    save_lock(ad, lock)
    print(f"\n{built} built, {skipped} unchanged")
    return 0


# --------------------------------------------------------------------------- upload

def quota(*args: str) -> int:
    sys.stdout.flush()  # keep our lines ahead of the child's output
    return subprocess.run([sys.executable, str(QUOTA), *args]).returncode


def upload_one(path: Path, name: str, api_key: str, creator: dict) -> str:
    import requests  # noqa: PLC0415 - only needed for uploads

    request = {"assetType": "Audio", "displayName": name,
               "description": "Original audio uploaded with roblox-ai-studio own-audio.",
               "creationContext": {"creator": creator}}
    files = {"request": (None, json.dumps(request), "application/json"),
             "fileContent": (path.name, path.read_bytes(), "audio/ogg")}
    resp = requests.post(ASSETS_URL, headers={"x-api-key": api_key}, files=files, timeout=180)
    if resp.status_code >= 400:
        raise SystemExit(f"upload failed {resp.status_code}: {resp.text}")
    body = resp.json()
    op = body.get("operationId") or body.get("path", "").rsplit("/", 1)[-1]
    deadline, delay = time.time() + 300, 2.0
    while time.time() < deadline:
        r = requests.get(OPERATION_URL.format(op=op), headers={"x-api-key": api_key}, timeout=60)
        if r.status_code >= 400:
            raise SystemExit(f"operation poll failed {r.status_code}: {r.text}")
        b = r.json()
        if b.get("done"):
            if "error" in b:
                raise SystemExit(f"asset job failed: {b['error']}")
            return str(b.get("response", b).get("assetId"))
        time.sleep(delay)
        delay = min(delay * 1.5, 15.0)
    raise SystemExit(f"operation {op} not done after 300s; re-poll later instead of re-uploading")


def cmd_upload(a) -> int:
    ad = audio_dir(a.game)
    lock = load_lock(ad)
    todo = []
    for stem, e in sorted(lock["sounds"].items()):
        built = ad / e.get("build", "")
        if not built.is_file():
            continue
        # Hash cache: an asset id stays valid while the built file is byte-identical.
        if e.get("asset_id") and e.get("uploaded_sha256") == sha256(built):
            continue
        todo.append((stem, built))
    if not todo:
        print("nothing to upload: every built file already has an asset id for its current hash")
        return 0
    print(f"{len(todo)} file(s) to upload:")
    for stem, built in todo:
        print(f"  {stem}  ({built.stat().st_size / 1024:.0f} KB)")
    if quota("estimate", "opencloud-audio", "--op", "audio-upload", "--count", str(len(todo))) == 2 \
            and not a.allow_over_quota:
        print("\nwould exceed the Open Cloud audio quota: ask the user (quota-guard) or upload fewer files")
        return 2
    if not a.yes:
        print("\ndry run. After the user approves (quota-guard), rerun with --yes")
        return 0

    api_key = os.environ.get("ROBLOX_API_KEY")
    if not api_key:
        raise SystemExit("ROBLOX_API_KEY is not set (Open Cloud key with Assets read+write)")
    group, user = os.environ.get("ROBLOX_GROUP_ID"), os.environ.get("ROBLOX_USER_ID")
    if not (group or user):
        raise SystemExit("set ROBLOX_USER_ID or ROBLOX_GROUP_ID (the creator that owns the uploads)")
    creator = {"groupId": group} if group else {"userId": user}
    for stem, built in todo:
        asset_id = upload_one(built, stem, api_key, creator)
        e = lock["sounds"][stem]
        e.update({"asset_id": asset_id, "uploaded_sha256": sha256(built),
                  "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        save_lock(ad, lock)  # after each file, so a failure halfway loses nothing
        quota("log", "opencloud-audio", "--op", "audio-upload", "--note", f"{a.game}/{stem}")
        print(f"uploaded {stem} -> rbxassetid://{asset_id}")
    return 0


# --------------------------------------------------------------------------- bank

def load_emitter():
    """Import SyphoDev's roblox-sfx emitter so the bank format has one source of truth."""
    if not (SFX_EMITTER / "emit_bank.py").exists():
        raise SystemExit(f"roblox-sfx not installed at {SFX_EMITTER}; run scripts/setup")
    sys.path.insert(0, str(SFX_EMITTER))
    import emit_bank  # noqa: PLC0415
    return emit_bank


def cmd_bank(a) -> int:
    eb = load_emitter()
    ad = audio_dir(a.game)
    lock = load_lock(ad)
    sounds = []
    if a.merge:  # Creator Store sounds picked by roblox-sfx
        sounds += json.loads(Path(a.merge).read_text(encoding="utf-8")).get("sounds", [])
    taken = {s["role"] for s in sounds}
    missing = []
    for stem, e in sorted(lock["sounds"].items()):
        if not e.get("asset_id"):
            missing.append(stem)
            continue
        if stem in taken:
            raise SystemExit(f"role {stem!r} exists in both banks; rename the WAV or the roblox-sfx role")
        cat = e.get("category", stem.split("_", 1)[0])
        sounds.append({"role": stem, "id": int(e["asset_id"]), "length": e["seconds"],
                       "volume": DEFAULT_VOLUME.get(cat, 0.5), "looped": cat in LOOPED,
                       "name": stem, "creator": "own"})
    # Keep roblox-sfx's type block verbatim (the format contract); only the comment differs.
    type_block = eb.BANK_HEAD[eb.BANK_HEAD.index("export type Entry"):]
    head = (
        "--!strict\n"
        "-- SoundBank: every sound this game uses, by role.\n"
        "--\n"
        "-- GENERATED by the own-audio skill in the roblox-sfx format. Do not hand-edit:\n"
        "-- re-run `audio.py bank`.\n"
        "--\n"
        "-- Entries with creator = \"own\" are original audio uploaded through Open Cloud;\n"
        "-- their `length` comes from ffprobe on the uploaded file. Any other entries were\n"
        "-- merged from a roblox-sfx manifest (Creator Store assets used by id).\n"
        "\n" + type_block)
    rows = []
    for s in sorted(sounds, key=lambda x: x["role"]):
        rows.append(
            f"\t[{eb.lua_str(s['role'])}] = {{\n"
            f"\t\tid = {s['id']},\n"
            f"\t\tlength = {s['length']},\n"
            f"\t\tvolume = {s['volume']},\n"
            f"\t\tlooped = {str(s['looped']).lower()},\n"
            f"\t\tname = {eb.lua_str(s['name'])},\n"
            f"\t\tcreator = {eb.lua_str(s['creator'])},\n"
            f"\t}},")
    out = Path(a.out) if a.out else ad / "bank"
    out.mkdir(parents=True, exist_ok=True)
    eb.write_lf(out / "SoundBank.luau", head + "\n".join(rows) + "\n" + eb.BANK_TAIL)
    eb.write_lf(out / "Sfx.luau", eb.SFX)
    print(f"{out / 'SoundBank.luau'}  {len(rows)} roles  -> src/shared/Config/")
    print(f"{out / 'Sfx.luau'}  -> src/shared/")
    if missing:
        print(f"not in the bank (no asset id yet): {', '.join(missing)}")
    return 0


# --------------------------------------------------------------------------- main

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "build", "upload", "bank"):
        p = sub.add_parser(name)
        p.add_argument("--game", required=True, help="game name under ROBLOX_GAMES_HOME, or a path")
        if name == "build":
            p.add_argument("--force", action="store_true", help="rebuild even if unchanged")
        if name == "upload":
            p.add_argument("--yes", action="store_true", help="actually upload (default: dry run)")
            p.add_argument("--allow-over-quota", action="store_true",
                           help="only after the user explicitly accepts going over")
        if name == "bank":
            p.add_argument("--merge", help="roblox-sfx manifest.json to merge (Creator Store sounds)")
            p.add_argument("--out", help="output folder (default: assets/audio/bank)")
    a = ap.parse_args()
    return {"check": cmd_check, "build": cmd_build, "upload": cmd_upload, "bank": cmd_bank}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
