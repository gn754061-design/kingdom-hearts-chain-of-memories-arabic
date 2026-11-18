#!/usr/bin/env python3
"""Dynamically patch Arabic glyph blob and widths into the built ROM using com_us.map."""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "build/us/com_us.gba"
MAP = ROOT / "build/us/com_us.map"
WIDTHS = ROOT / "build/fonts/arabic_widths.json"
BLOB = ROOT / "build/fonts/arabic_glyphs.bin"

BASE = 0x08000000
FIRST_SLOT = 0x80


def find_symbol(map_text, symbol_name):
    for line in map_text.splitlines():
        if symbol_name in line:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0].startswith("0x"):
                return int(parts[0], 16)
    return None


def main():
    if not ROM.exists():
        sys.exit(f"ROM not found at {ROM}")
    if not MAP.exists():
        sys.exit(f"Map file not found at {MAP}")

    map_text = MAP.read_text(encoding="utf-8")
    frames_addr = find_symbol(map_text, "gMsgLatinFontFrames")
    tiles_addr = find_symbol(map_text, "gMsgLatinFontTiles")

    if not frames_addr:
        sys.exit("Could not find gMsgLatinFontFrames in map file")
    if not tiles_addr:
        sys.exit("Could not find gMsgLatinFontTiles in map file")

    rom = bytearray(ROM.read_bytes())

    # Find sLatinGlyphWidths table dynamically (exact table start):
    pat = struct.pack("<9H", 0, 4, 4, 5, 5, 6, 8, 8, 8)
    idx = rom.find(pat)
    if idx == -1:
        sys.exit("Could not locate sLatinGlyphWidths pattern in ROM")
    width_table_addr = BASE + idx

    print(f"Dynamic addresses resolved:")
    print(f"  gMsgLatinFontFrames : 0x{frames_addr:08X}")
    print(f"  gMsgLatinFontTiles  : 0x{tiles_addr:08X}")
    print(f"  sLatinGlyphWidths   : 0x{width_table_addr:08X}")

    # Set inter-word space (slot 0x20) to 5 pixels (Golden Sun standard)
    struct.pack_into("<H", rom, width_table_addr - BASE + 0x20 * 2, 5)
    print("  Slot 0x20 (space) width set to 5 px")

    widths = json.loads(WIDTHS.read_text(encoding="utf-8"))
    blob = BLOB.read_bytes()
    num_slots = len(blob) // 128
    assert len(blob) % 128 == 0, f"Invalid blob size: {len(blob)}"

    written = []
    for i in range(num_slots):
        slot = FIRST_SLOT + i
        frame_ptr = struct.unpack_from("<I", rom, frames_addr - BASE + slot * 4)[0]
        tile_index = struct.unpack_from("<H", rom, frame_ptr - BASE + 6)[0]
        addr = tiles_addr - BASE + tile_index * 32
        chunk = blob[i * 128 : (i + 1) * 128]
        if not any(chunk):
            sys.exit(f"Slot 0x{slot:02X} blob chunk is empty")
        rom[addr : addr + 128] = chunk

        slot_w = int(widths.get(str(slot), 8))
        woff = width_table_addr - BASE + slot * 2
        struct.pack_into("<H", rom, woff, slot_w)
        written.append((slot, tile_index, addr + BASE, slot_w))

    ROM.write_bytes(rom)
    print(f"Successfully patched {len(written)} glyphs into ROM.")
    for slot, ti, rom_addr, w in written[:4]:
        print(f"  Slot 0x{slot:02X}: tile {ti:3d} @ 0x{rom_addr:08X}, width={w}")
    print(f"  ...")
    for slot, ti, rom_addr, w in written[-2:]:
        print(f"  Slot 0x{slot:02X}: tile {ti:3d} @ 0x{rom_addr:08X}, width={w}")


if __name__ == "__main__":
    main()
