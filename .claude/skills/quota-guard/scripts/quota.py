#!/usr/bin/env python3
"""Track free-tier quota use against the limits in docs/quotas.md.

    python quota.py status [SERVICE]
    python quota.py estimate SERVICE AMOUNT            # AMOUNT in the service's unit
    python quota.py estimate SERVICE --op OP [--count N]
    python quota.py log SERVICE AMOUNT [--note TEXT]
    python quota.py log SERVICE --op OP [--count N] [--note TEXT]
    python quota.py ops                                # list operation costs

Limits and per-operation costs are parsed from the two "machine" tables in
docs/quotas.md, the single source of truth. Use is appended to
work/quota-ledger.json (gitignored). Standard library only.

estimate exit codes: 0 fits, 2 would exceed the limit (ask the user first),
1 error. A service with no published limit always returns 0 and says so.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
QUOTAS_MD = REPO / "docs" / "quotas.md"
LEDGER = Path(os.environ.get("QUOTA_LEDGER", REPO / "work" / "quota-ledger.json"))


@dataclass
class Service:
    key: str
    name: str
    limit: float | None
    unit: str
    window: str
    source: str
    verified: str


@dataclass
class Op:
    key: str
    service: str
    cost: float


# --------------------------------------------------------------------------- parsing

def _rows(section: str, text: str) -> list[list[str]]:
    """Table rows under the first heading that contains `section`, keyed by a `backticked` first cell."""
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = section in line
            continue
        if inside and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            m = re.fullmatch(r"`([^`]+)`", cells[0])
            if m:
                out.append([m.group(1), *cells[1:]])
    return out


def load_tables() -> tuple[dict[str, Service], dict[str, Op]]:
    text = QUOTAS_MD.read_text(encoding="utf-8")
    services = {}
    for r in _rows("Límites (tabla máquina)", text):
        key, name, limit, unit, window, source, verified = r[:7]
        services[key] = Service(key, name, None if limit in ("-", "") else float(limit), unit, window,
                                source, verified)
    ops = {}
    for r in _rows("Costes por operación (tabla máquina)", text):
        key, service, cost = r[:3]
        ops[key] = Op(key, service, float(cost))
    if not services:
        raise SystemExit(f"no machine table found in {QUOTAS_MD}")
    return services, ops


# --------------------------------------------------------------------------- windows

def now() -> datetime:
    return datetime.now(timezone.utc)


def parse_window(window: str) -> tuple[str, timedelta | None]:
    if window == "daily-utc":
        return "daily-utc", None
    m = re.fullmatch(r"rolling-(\d+)([smhd])", window)
    if m:
        n, u = int(m.group(1)), m.group(2)
        return "rolling", timedelta(**{{"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}[u]: n})
    return "none", None


def window_start(svc: Service, t: datetime) -> datetime | None:
    kind, span = parse_window(svc.window)
    if kind == "daily-utc":
        return t.replace(hour=0, minute=0, second=0, microsecond=0)
    if kind == "rolling":
        return t - span
    return None


def next_reset(svc: Service, entries: list[dict], t: datetime) -> str:
    kind, span = parse_window(svc.window)
    if kind == "daily-utc":
        return (t.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat(
            timespec="minutes")
    if kind == "rolling" and entries:
        oldest = min(datetime.fromisoformat(e["ts"]) for e in entries)
        return f"{(oldest + span).isoformat(timespec='minutes')} (se libera la entrada más antigua)"
    return "-"


# --------------------------------------------------------------------------- ledger

def read_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    try:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise SystemExit(f"{LEDGER} is not valid JSON: {exc}") from exc
    return data.get("entries", [])


def write_ledger(entries: list[dict]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps({"version": 1, "entries": entries}, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")


def in_window(svc: Service, entries: list[dict], t: datetime) -> list[dict]:
    start = window_start(svc, t)
    mine = [e for e in entries if e["service"] == svc.key]
    if start is None:
        return mine
    return [e for e in mine if datetime.fromisoformat(e["ts"]) >= start]


def usage(svc: Service, entries: list[dict], t: datetime) -> tuple[float, float | None, list[dict]]:
    current = in_window(svc, entries, t)
    used = sum(e["amount"] for e in current)
    remaining = None if svc.limit is None else svc.limit - used
    return used, remaining, current


# --------------------------------------------------------------------------- commands

def fmt(x: float | None) -> str:
    if x is None:
        return "-"
    return f"{x:.0f}" if float(x).is_integer() else f"{x:.1f}"


def resolve_amount(a, services, ops) -> tuple[Service, float, str | None]:
    if a.service not in services:
        raise SystemExit(f"unknown service {a.service!r}. Known: {', '.join(services)}")
    svc = services[a.service]
    if a.op:
        if a.op not in ops:
            raise SystemExit(f"unknown op {a.op!r}. Run: quota.py ops")
        op = ops[a.op]
        if op.service != svc.key:
            raise SystemExit(f"op {a.op} belongs to {op.service}, not {svc.key}")
        return svc, op.cost * a.count, a.op
    if a.amount is None:
        raise SystemExit("give an AMOUNT or --op")
    return svc, a.amount, None


def cmd_status(a, services, ops) -> int:
    t, entries = now(), read_ledger()
    keys = [a.service] if a.service else list(services)
    print(f"Cupos (UTC {t.isoformat(timespec='minutes')}) · fuente: docs/quotas.md · registro: {LEDGER}")
    print(f"{'servicio':24} {'usado':>9} {'límite':>9} {'queda':>9}  {'unidad':12} {'ventana':12} reinicio")
    for k in keys:
        if k not in services:
            raise SystemExit(f"unknown service {k!r}")
        svc = services[k]
        used, remaining, current = usage(svc, entries, t)
        flag = "  ⚠️" if remaining is not None and svc.limit and remaining <= 0.1 * svc.limit else ""
        print(f"{k:24} {fmt(used):>9} {fmt(svc.limit):>9} {fmt(remaining):>9}  {svc.unit:12} {svc.window:12} "
              f"{next_reset(svc, current, t)}{flag}")
    return 0


def cmd_estimate(a, services, ops) -> int:
    svc, amount, op = resolve_amount(a, services, ops)
    used, remaining, current = usage(svc, read_ledger(), now())
    label = f"{a.count} × {op}" if op else "manual"
    print(f"{svc.key}: esta llamada ≈ {fmt(amount)} {svc.unit} ({label})")
    if svc.limit is None:
        print(f"  sin límite publicado ({svc.source}); usado en ventana: {fmt(used)} {svc.unit}")
        return 0
    after = remaining - amount
    print(f"  usado {fmt(used)} / {fmt(svc.limit)} · queda {fmt(remaining)} · después quedaría {fmt(after)}")
    if after < 0:
        print(f"  EXCEDE el cupo. Próximo reinicio: {next_reset(svc, current, now())}. Pregunta al usuario "
              f"o usa el respaldo (ver SKILL.md).")
        return 2
    if after < 0.1 * svc.limit:
        print("  Aviso: quedará menos del 10 % del cupo.")
    return 0


def cmd_log(a, services, ops) -> int:
    svc, amount, op = resolve_amount(a, services, ops)
    entries = read_ledger()
    entry = {"ts": now().isoformat(timespec="seconds"), "service": svc.key, "amount": amount, "unit": svc.unit}
    if op:
        entry["op"], entry["count"] = op, a.count
    if a.note:
        entry["note"] = a.note
    entries.append(entry)
    write_ledger(entries)
    used, remaining, _ = usage(svc, entries, now())
    print(f"registrado: {fmt(amount)} {svc.unit} en {svc.key} · usado {fmt(used)} · queda {fmt(remaining)}")
    return 0


def cmd_ops(a, services, ops) -> int:
    print(f"{'operación':22} {'servicio':24} coste")
    for op in ops.values():
        unit = services[op.service].unit if op.service in services else "?"
        print(f"{op.key:22} {op.service:24} {fmt(op.cost)} {unit}")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status")
    s.add_argument("service", nargs="?")
    for name in ("estimate", "log"):
        p = sub.add_parser(name)
        p.add_argument("service")
        p.add_argument("amount", nargs="?", type=float)
        p.add_argument("--op")
        p.add_argument("--count", type=int, default=1)
        if name == "log":
            p.add_argument("--note")
    sub.add_parser("ops")
    a = ap.parse_args()
    services, ops = load_tables()
    return {"status": cmd_status, "estimate": cmd_estimate, "log": cmd_log, "ops": cmd_ops}[a.cmd](a, services, ops)


if __name__ == "__main__":
    sys.exit(main())
