#!/usr/bin/env python3
"""Deduplicated Arabic glyph bank (128 slots) using Rooyin font (Golden Sun quality) with drop shadow."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROOYIN_FONT_JSON = ROOT / "fonts/rooyin_font.json"
RENDER_LABELS_JSON = ROOT / "fonts/render_labels.json"
MAP_OUT = ROOT / "build/fonts/arabic_slot_map.json"
BLOB_OUT = ROOT / "build/fonts/arabic_glyphs.bin"
WIDTHS_OUT = ROOT / "build/fonts/arabic_widths.json"

CELL = 16
FIRST_SLOT, LAST_SLOT = 0x80, 0xFF
TARGET_BASELINE = 10  # KHCOM Latin baseline is row 10 (shadow row 11)
ROOYIN_BASELINE = 11  # Rooyin connector is row 11

BASE_TO_ISO = {
    0x0621: 0xFE80, 0x0622: 0xFE81, 0x0623: 0xFE83, 0x0624: 0xFE85,
    0x0625: 0xFE87, 0x0626: 0xFE89, 0x0627: 0xFE8D, 0x0628: 0xFE8F,
    0x0629: 0xFE93, 0x062A: 0xFE95, 0x062B: 0xFE99, 0x062C: 0xFE9D,
    0x062D: 0xFEA1, 0x062E: 0xFEA5, 0x062F: 0xFEA9, 0x0630: 0xFEAB,
    0x0631: 0xFEAD, 0x0632: 0xFEAF, 0x0633: 0xFEB1, 0x0634: 0xFEB5,
    0x0635: 0xFEB9, 0x0636: 0xFEBD, 0x0637: 0xFEC1, 0x0638: 0xFEC5,
    0x0639: 0xFEC9, 0x063A: 0xFECD, 0x0641: 0xFED1, 0x0642: 0xFED5,
    0x0643: 0xFED9, 0x0644: 0xFEDD, 0x0645: 0xFEE1, 0x0646: 0xFEE5,
    0x0647: 0xFEE9, 0x0648: 0xFEED, 0x0649: 0xFEEF, 0x064A: 0xFEF1,
}


NON_CONNECTING_CPS = {
    # Alif forms
    0xFE8D, 0xFE8E, 0xFE81, 0xFE82, 0xFE83, 0xFE84, 0xFE87, 0xFE88,
    # Dal, Dhal forms
    0xFEA9, 0xFEAA, 0xFEAB, 0xFEAC,
    # Raa, Zay forms
    0xFEAD, 0xFEAE, 0xFEAF, 0xFEB0,
    # Waw forms
    0xFEED, 0xFEEE, 0xFE85, 0xFE86,
    # Isolated forms that never connect
    0xFE93, 0xFE80, 0xFEEF,
    # Lam-Alif ligatures (end with Alif, so non-connecting on left in visual order)
    0xFEF5, 0xFEF6, 0xFEF7, 0xFEF8, 0xFEF9, 0xFEFA, 0xFEFB, 0xFEFC,
}


def pack(cell):
    out = bytearray()
    for ty in range(2):
        for tx in range(2):
            tile = bytearray(32)
            for y in range(8):
                for x in range(0, 8, 2):
                    lo = cell[ty * 8 + y][tx * 8 + x]
                    hi = cell[ty * 8 + y][tx * 8 + x + 1] if tx * 8 + x + 1 < 16 else 0
                    tile[y * 4 + x // 2] = (hi << 4) | lo
            out += tile
    return bytes(out)


def main():
    if not ROOYIN_FONT_JSON.exists() or not RENDER_LABELS_JSON.exists():
        raise FileNotFoundError(f"Rooyin font data not found in {ROOT / 'fonts'}")

    rooyin = json.loads(ROOYIN_FONT_JSON.read_text(encoding="utf-8"))
    render_labels = json.loads(RENDER_LABELS_JSON.read_text(encoding="utf-8"))

    label_to_cp = {v: int(k, 16) for k, v in render_labels.items()}
    cp_to_form = {label_to_cp[f["label"]]: f for f in rooyin["forms"] if f["label"] in label_to_cp}

    cps_path = ROOT / "build/fonts/corpus_cps.json"
    if not cps_path.exists():
        cps = list(range(0xFE70, 0xFF00))
    else:
        cps = json.loads(cps_path.read_text(encoding="utf-8"))

    fe_cps = sorted([c for c in cps if 0xFE70 <= c <= 0xFEFF])
    slot_cps = fe_cps + [0x060C, 0x061F, 0x0640]
    assert len(slot_cps) <= 128, f"Too many slots: {len(slot_cps)}"

    slot_map = {}
    blob = bytearray()
    widths = {}

    shift = TARGET_BASELINE - ROOYIN_BASELINE  # -1 to align with KHCOM baseline 10

    for i, cp in enumerate(slot_cps):
        slot = FIRST_SLOT + i
        grid = [[0] * CELL for _ in range(CELL)]

        if cp not in cp_to_form:
            raise KeyError(f"Codepoint 0x{cp:04X} missing from Rooyin forms")

        f = cp_to_form[cp]
        orig_w = f["w"]
        left_pad = 1 if cp in NON_CONNECTING_CPS else 0
        adv = orig_w + left_pad

        # Connector baseline fixes for Rooyin font
        rows = [list(r) for r in f["rows"]]
        if cp == 0xFE88 and len(rows) > 11 and len(rows[11]) > 1:  # إ:fin
            rows[11][1] = 1
        elif cp == 0xFE8C and len(rows) > 11 and len(rows[11]) >= 4:  # ئ:med
            rows[11][:4] = [1, 1, 1, 1]
        elif cp == 0xFEF3 and len(rows) > 11 and len(rows[11]) >= 4:  # ي:ini
            rows[11][:4] = [1, 1, 1, 1]
        elif cp == 0xFEF4 and len(rows) > 11 and len(rows[11]) >= 5:  # ي:med
            rows[11][:5] = [1, 1, 1, 1, 1]

        for y, r in enumerate(rows):
            ty = y + shift
            if 0 <= ty < CELL:
                for x in range(orig_w):
                    if r[x]:
                        grid[ty][x + left_pad] = 1

        # Shadow generation (palette index 2)
        # Bounded strictly to x < adv to prevent OBJ overlap clipping
        final_cell = [[0] * CELL for _ in range(CELL)]
        for y in range(CELL):
            for x in range(CELL):
                if grid[y][x] == 1:
                    final_cell[y][x] = 1
                elif x < adv:
                    has_body = (
                        (x > 0 and grid[y][x - 1] == 1) or
                        (y > 0 and grid[y - 1][x] == 1) or
                        (x > 0 and y > 0 and grid[y - 1][x - 1] == 1)
                    )
                    if has_body:
                        final_cell[y][x] = 2

        slot_map[f"0x{cp:04X}"] = slot
        widths[str(slot)] = adv
        blob += pack(final_cell)

    # Aliases
    for base, iso in BASE_TO_ISO.items():
        slot_map[f"0x{base:04X}"] = slot_map[f"0x{iso:04X}"]

    slot_map["0x06AF"] = slot_map["0xFED9"]
    slot_map["0xFB92"] = slot_map["0xFEDA"]
    slot_map["0xFB93"] = slot_map["0xFEDC"]
    slot_map["0xFB94"] = slot_map["0xFEDB"]

    for d in range(10):
        slot_map[f"0x{0x0660 + d:04X}"] = 0x0030 + d

    MAP_OUT.parent.mkdir(parents=True, exist_ok=True)
    MAP_OUT.write_text(json.dumps(slot_map, indent=1), encoding="utf-8", newline="\n")
    BLOB_OUT.write_bytes(blob)
    WIDTHS_OUT.write_text(json.dumps(widths, indent=1), encoding="utf-8", newline="\n")
    print(f"slots used: {len(slot_cps)} (0x{FIRST_SLOT:02X}-0x{FIRST_SLOT + len(slot_cps) - 1:02X}), blob={len(blob)}B (Rooyin font)")


if __name__ == "__main__":
    main()
