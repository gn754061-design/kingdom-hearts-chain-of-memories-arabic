#!/usr/bin/env python3
"""Generate and verify standard BPS patch for Kingdom Hearts: Chain of Memories."""
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_ROM = ROOT / "roms/base/Kingdom Hearts - Chain of Memories (USA).gba"
DST_ROM = ROOT / "build/khcom_us_arabic_final.gba"
OUT_BPS = ROOT / "build/khcom_us_arabic.bps"


def encode_varint(val):
    out = bytearray()
    while True:
        b = val & 0x7F
        val >>= 7
        if val == 0:
            out.append(b | 0x80)
            break
        out.append(b)
        val -= 1
    return bytes(out)


def encode_signed_varint(val):
    sign = 1 if val < 0 else 0
    val = -val if val < 0 else val
    return encode_varint((val << 1) | sign)


def decode_varint(data, offset):
    val = 0
    shift = 0
    while True:
        b = data[offset]
        offset += 1
        val += (b & 0x7F) << shift
        if b & 0x80:
            break
        shift += 7
        val += 1 << shift
    return val, offset


def main():
    if not SRC_ROM.exists():
        raise FileNotFoundError(f"Source ROM not found at {SRC_ROM}")
    if not DST_ROM.exists():
        raise FileNotFoundError(f"Target ROM not found at {DST_ROM}")

    src = SRC_ROM.read_bytes()
    dst = DST_ROM.read_bytes()

    src_crc = zlib.crc32(src) & 0xFFFFFFFF
    dst_crc = zlib.crc32(dst) & 0xFFFFFFFF

    patch = bytearray(b"BPS1")
    patch += encode_varint(len(src))
    patch += encode_varint(len(dst))
    patch += encode_varint(0)

    src_off = 0
    dst_off = 0
    n = len(src)

    while dst_off < n:
        # Check matching bytes
        m_len = 0
        while (dst_off + m_len < n) and (src[dst_off + m_len] == dst[dst_off + m_len]):
            m_len += 1
        if m_len > 0:
            diff = dst_off - src_off
            patch += encode_varint(((m_len - 1) << 2) | 2)  # SourceCopy
            patch += encode_signed_varint(diff)
            src_off = dst_off + m_len
            dst_off += m_len
        if dst_off >= n:
            break

        # Mismatch bytes
        d_len = 0
        while (dst_off + d_len < n) and (src[dst_off + d_len] != dst[dst_off + d_len]):
            d_len += 1
        if d_len > 0:
            patch += encode_varint(((d_len - 1) << 2) | 1)  # TargetRead
            patch += dst[dst_off : dst_off + d_len]
            dst_off += d_len

    patch += struct.pack("<II", src_crc, dst_crc)
    patch_crc = zlib.crc32(patch) & 0xFFFFFFFF
    patch += struct.pack("<I", patch_crc)

    OUT_BPS.parent.mkdir(parents=True, exist_ok=True)
    OUT_BPS.write_bytes(patch)
    print(f"BPS patch created: {OUT_BPS} ({len(patch)} bytes, {len(patch)/(1024*1024):.2f} MB)")

    # Verify decoding byte-for-byte
    p = 4
    src_size, p = decode_varint(patch, p)
    dst_size, p = decode_varint(patch, p)
    meta_size, p = decode_varint(patch, p)
    p += meta_size

    out = bytearray(dst_size)
    s_off = 0
    d_off = 0

    while p < len(patch) - 12:
        val, p = decode_varint(patch, p)
        mode = val & 3
        length = (val >> 2) + 1
        if mode == 0:
            out[d_off : d_off + length] = src[s_off : s_off + length]
            s_off += length
            d_off += length
        elif mode == 1:
            out[d_off : d_off + length] = patch[p : p + length]
            p += length
            d_off += length
        elif mode == 2:
            offset, p = decode_varint(patch, p)
            s_off += -(offset >> 1) if (offset & 1) else (offset >> 1)
            out[d_off : d_off + length] = src[s_off : s_off + length]
            s_off += length
            d_off += length
        elif mode == 3:
            raise NotImplementedError("TargetCopy")

    assert d_off == dst_size
    assert bytes(out) == dst, "Decoder mismatch!"
    print("Verification PASSED: Decoded ROM matches target byte-for-byte!")


if __name__ == "__main__":
    main()
