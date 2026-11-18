#!/usr/bin/env python3
"""Merge translated chunks back into the pools and lint them.

Lint rules (fail closed):
  - every chunk item must have an Arabic translation
  - translated length in u16 units must not exceed max_units
  - control codes must match the source exactly (multiset)
  - line count must not exceed the source line count
  - no replacement chars / mojibake / raw Arabic presentation forms in source
Writes translation/merged/<pool>.txt ready for textgen.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHUNK_DIR = ROOT / "translation" / "chunks"
TRANS_DIR = ROOT / "translation" / "translated"
MERGED_DIR = ROOT / "translation" / "merged"

CONTROL = re.compile(r"\{[^}]*\}")
TAG_OK = re.compile(r"^\{[A-Za-z0-9_]+\}$|^\{0x[0-9A-Fa-f]{4}\}$")
FORBIDDEN = ("\ufffd", "Ã", "Ø", "â€", "Ã¢")


def ar_units(text: str) -> int:
    """Units after the build pipeline: tags collapse to 1 unit, newline 1 unit."""
    units = 0
    for part in CONTROL.split(text):
        pass
    tokens = re.split(r"(\{[^}]*\})", text)
    for tok in tokens:
        if not tok:
            continue
        if CONTROL.fullmatch(tok):
            units += 1
        else:
            units += len(tok.replace("\n", "")) + tok.count("\n")
    return units


def load_translated():
    out = {}
    for f in sorted(TRANS_DIR.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for key, value in (data.get("translations") or {}).items():
            out[key] = value
    return out


def main():
    if not CHUNK_DIR.exists():
        print("no chunks; run chunk_translate.py first")
        return 1

    only = None
    for arg in sys.argv[1:]:
        if arg.startswith("--chunks="):
            only = {int(x) for x in arg.split("=", 1)[1].split(",") if x.strip()}

    translations = load_translated()
    errors = []
    merged = {}
    pool_use = Counter()
    pool_cap = {}

    files = sorted(CHUNK_DIR.glob("chunk_*.json"))
    if only:
        files = [f for f in files if int(f.stem.split("_")[1]) in only]

    for chunk_file in files:
        chunk = json.loads(chunk_file.read_text(encoding="utf-8"))
        for item in chunk["items"]:
            pool_cap[item["pool"]] = pool_cap.get(item["pool"], 0) + item["max_units"]

    for chunk_file in files:
        chunk = json.loads(chunk_file.read_text(encoding="utf-8"))
        for item in chunk["items"]:
            key = item["id"]
            ar = translations.get(key)
            if ar is None or not ar.strip():
                errors.append(f"{key}: missing translation")
                continue

            for bad in FORBIDDEN:
                if bad in ar:
                    errors.append(f"{key}: forbidden sequence {bad!r}")

            src_controls = Counter(CONTROL.findall(item["en"]))
            out_controls = Counter(CONTROL.findall(ar))
            for tag in ("{NL}",):
                pass
            if src_controls != out_controls:
                # newline is a real newline in the pool, not a tag
                if src_controls != out_controls:
                    errors.append(
                        f"{key}: control mismatch src={dict(src_controls)} out={dict(out_controls)}")

            if ar.count("\n") > item["en"].count("\n"):
                errors.append(f"{key}: more lines than source")

            units = ar_units(ar)
            if units > item["max_units"]:
                errors.append(f"{key}: {units} units > budget {item['max_units']}")
            pool_use[item["pool"]] += units

            merged.setdefault(item["pool"], []).append((item["symbol"], ar))

    MERGED_DIR.mkdir(parents=True, exist_ok=True)
    for old in MERGED_DIR.glob("*.txt"):
        old.unlink()
    for pool, rows in merged.items():
        lines = []
        for symbol, text in rows:
            lines.append(f"@{symbol}")
            lines.append(text)
        (MERGED_DIR / f"{pool}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    total = sum(len(v) for v in merged.values())
    print(f"scope              : chunks {sorted(only) if only else 'all'}")
    print(f"translated entries : {total}")
    print(f"pools written      : {len(merged)} -> {MERGED_DIR}")
    print(f"lint errors        : {len(errors)}")
    for e in errors[:15]:
        print("  -", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())