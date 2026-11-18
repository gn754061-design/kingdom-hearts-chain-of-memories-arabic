#!/usr/bin/env python3
"""Generate the Arabic glyph bank for KHCoM: codepoint-indexed, 128 bytes/glyph."""
import sys
import freetype
from pathlib import Path

FONT = "/work/sandbox/khcom/fonts/Arabixel-Basic.ttf"
OUT_C = Path("/work/sandbox/khcom/src/msg/arabic_font.c")
OUT_H = Path("/work/sandbox/khcom/include/msg/arabic_font.h")
PREVIEW = Path("/work/sandbox/khcom/build/fonts/arabic_atlas_preview.png")

PIXEL_SIZE = 12
BASELINE = 12
CELL = 16

# slot -> codepoint
def slots():
    out = []
    for cp in range(0x0600, 0x0700):
        out.append(cp)
    for cp in range(0xFE70, 0xFF00):
        out.append(cp)
    return out

def render(ft, cp):
    gid = ft.get_char_index(cp)
    if gid == 0:
        return None
    ft.load_glyph(gid, freetype.FT_LOAD_RENDER)
    bmp = ft.glyph.bitmap
    if bmp.rows == 0 or bmp.width == 0:
        return None
    cell = [[0] * CELL for _ in range(CELL)]
    top = BASELINE - ft.glyph.bitmap_top
    for y in range(bmp.rows):
        py = top + y
        if not (0 <= py < CELL):
            continue
        for x in range(bmp.width):
            px = ft.glyph.bitmap_left + x
            if not (0 <= px < CELL):
                continue
            v = bmp.buffer[y * bmp.pitch + x]
            if v >= 96:
                cell[py][px] = 1
    return cell

def tiles(cell):
    out = bytearray()
    for ty in range(2):
        for tx in range(2):
            tile = bytearray(32)
            for y in range(8):
                for x in range(0, 8, 2):
                    lo = 15 if cell[ty*8+y][tx*8+x] else 0
                    hi = 15 if (tx*8+x+1 < 16 and cell[ty*8+y][tx*8+x+1]) else 0
                    tile[y*4 + x//2] = (hi << 4) | lo
            out += tile
    return bytes(out)

def main():
    ft = freetype.Face(FONT)
    ft.set_pixel_sizes(0, PIXEL_SIZE)
    cps = slots()
    tiles_blob = bytearray()
    widths = []
    present = 0
    zero_glyphs = []

    for i, cp in enumerate(cps):
        cell = render(ft, cp)
        if cell is None:
            tiles_blob += b"\x00" * 128
            widths.append(0)
            continue
        blob = tiles(cell)
        if not any(blob):
            zero_glyphs.append(cp)
        else:
            present += 1
        tiles_blob += blob
        w = round(ft.glyph.advance.x / 64.0)
        widths.append(max(1, min(15, w)))

    assert len(tiles_blob) == len(cps) * 128, (len(tiles_blob), len(cps))

    # write C
    OUT_C.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_C, "w", encoding="utf-8", newline="\n") as f:
        f.write('#include "types.h"\n#include "msg/arabic_font.h"\n\n')
        f.write("// %d slots, 128 bytes per glyph, indexed by codepoint offset.\n\n" % len(cps))
        f.write('const u32 gArabicFontTiles[] __attribute__((section(".arabic_rodata"))) = {\n')
        for i in range(0, len(tiles_blob), 32):
            chunk = tiles_blob[i:i+32]
            words = []
            for j in range(0, 32, 4):
                words.append("0x%08X" % int.from_bytes(chunk[j:j+4], "little"))
            f.write("    " + ", ".join(words) + ",\n")
        f.write("};\n\n")
        f.write('const u8 sArabicWidths[] __attribute__((section(".arabic_rodata"))) = {\n')
        for i in range(0, len(widths), 16):
            f.write("    " + ", ".join(str(w) for w in widths[i:i+16]) + ",\n")
        f.write("};\n")

    with open(OUT_H, "w", encoding="utf-8", newline="\n") as f:
        f.write("#ifndef GUARD_ARABIC_FONT_H\n#define GUARD_ARABIC_FONT_H\n\n")
        f.write("#include \"global.h\"\n\n")
        f.write("#define ARABIC_SLOT_COUNT %d\n\n" % len(cps))
        f.write("extern const u32 gArabicFontTiles[];\n")
        f.write("extern const u8 sArabicWidths[];\n\n")
        f.write("s32 ArabicGlyphForChar(u16 ch);\n\n")
        f.write("#endif\n")

    print("slots:", len(cps), "present:", present, "zero-bitmap:", len(zero_glyphs))
    print("tile bytes:", len(tiles_blob))
    print("max width:", max(widths), "avg:", round(sum(widths)/max(1,sum(1 for w in widths if w)),2))
    print("first zero cps:", [hex(c) for c in zero_glyphs[:8]])

if __name__ == "__main__":
    main()
