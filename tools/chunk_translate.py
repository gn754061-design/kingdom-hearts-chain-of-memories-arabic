#!/usr/bin/env python3
"""Split the editable text pools into translation chunks.

Each chunk file holds ~70 entries: symbol, English text, unit budget and the
control codes that must survive translation. Budgets come from the original
ROM allocation (config/text/*.yaml fragments/macros) so reinsertion cannot
grow the ROM.
"""
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
POOL_DIR = ROOT / "assets" / "us" / "text"
CFG_DIR = ROOT / "config" / "text"
OUT_DIR = ROOT / "translation" / "chunks"
ENTRIES_PER_CHUNK = 70

HEADER = re.compile(r"^@(\w+)\s*$")
CONTROL = re.compile(r"\{[^}]*\}")


def load_budgets():
    """symbol -> unit budget from the ROM manifest."""
    budgets = {}
    for y in CFG_DIR.glob("*.yaml"):
        doc = yaml.safe_load(open(y, encoding="utf-8"))
        for ver, spec in (doc.get("fragments") or {}).items():
            for frag in spec:
                entries = frag.get("entries") or []
                if len(entries) < 2:
                    continue
                total = frag.get("end", 0) - frag.get("start", 0)
                per = max(1, total // 2 // len(entries))
                for name in entries:
                    if isinstance(name, dict):
                        name = name.get("name")
                    if isinstance(name, str):
                        budgets[name] = per
        for ver, spec in (doc.get("objects") or {}).items():
            if not isinstance(spec, dict):
                continue
            size = spec.get("size")
            if not size:
                continue
            stride = spec.get("stride")
            if stride:
                for i, name in enumerate(doc.get("entries") or []):
                    if isinstance(name, str):
                        budgets[name] = stride // 2
                    elif isinstance(name, dict) and isinstance(name.get("name"), str):
                        budgets[name["name"]] = stride // 2
    return budgets


def parse_pool(path):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    entries = []
    current = None
    buf = []
    for line in text.split("\n"):
        m = HEADER.match(line)
        if m:
            if current:
                entries.append((current, "\n".join(buf)))
            current, buf = m.group(1), []
        elif current:
            buf.append(line)
    if current:
        entries.append((current, "\n".join(buf)))
    return [(s, t.strip("\n")) for s, t in entries if t.strip()]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.json"):
        old.unlink()

    budgets = load_budgets()
    pools = {}
    for pool in sorted(POOL_DIR.glob("*.txt")):
        pools[pool.stem] = parse_pool(pool)

    # fair share per pool: the pool must keep its original u16 footprint, so an
    # entry may use its English length or its share of the pool, whichever is larger
    share = {}
    for name, rows in pools.items():
        total = sum(len(t) + t.count("\n") for _, t in rows)
        per = max(1, -(-total // max(1, len(rows))))
        for symbol, _ in rows:
            share[symbol] = per

    entries = []
    for pool_name, rows in pools.items():
        for symbol, text in rows:
            controls = sorted(set(CONTROL.findall(text)))
            units = len(text) + text.count("\n")
            budget = max(units, share.get(symbol, units), budgets.get(symbol, 0))
            entries.append({
                "id": f"{pool_name}:{symbol}",
                "pool": pool_name,
                "symbol": symbol,
                "en": text,
                "max_units": int(budget),
                "units": int(units),
                "controls": controls,
                "lines": text.count("\n") + 1,
            })

    chunks = [entries[i:i + ENTRIES_PER_CHUNK] for i in range(0, len(entries), ENTRIES_PER_CHUNK)]
    for i, chunk in enumerate(chunks, 1):
        payload = {
            "chunk": i,
            "chunks_total": len(chunks),
            "entries": len(chunk),
            "lines": sum(e["lines"] for e in chunk),
            "items": chunk,
        }
        p = OUT_DIR / f"chunk_{i:03d}.json"
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")

    total_units = sum(e["units"] for e in entries)
    tight = [e for e in entries if e["units"] > e["max_units"]]
    print(f"pools              : {len(list(POOL_DIR.glob('*.txt')))}")
    print(f"entries            : {len(entries)}")
    print(f"chunks (3/task)    : {len(chunks)} -> tasks: {(len(chunks)+2)//3}")
    print(f"total u16 units    : {total_units}")
    print(f"entries over budget: {len(tight)}")


if __name__ == "__main__":
    main()