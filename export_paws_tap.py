#!/usr/bin/env python3
"""
PAWS Database Tape Exporter (SpeccyLift / Standalone Utility)
Extracts authentic PAWS (Professional Adventure Writer) database memory blocks
from ZX Spectrum snapshots (.SNA, .Z80) or compiled release tapes (.TAP)
and outputs a standard Sinclair .TAP file with Blocks 'A' and 'B'.

Can be loaded directly into PAWS running in any ZX Spectrum emulator (ZEsarUX, Fuse, etc.)
via Option 'J' ("Load Base de datos" in Opciones Extra).
"""

import sys
import os
import struct

# Local import for standalone execution
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from snapshot import load_sna, load_z80


def make_tap_block(flag: int, payload: bytes) -> bytes:
    data = bytes([flag]) + payload
    checksum = 0
    for b in data:
        checksum ^= b
    full_block = data + bytes([checksum])
    length_header = struct.pack("<H", len(full_block))
    return length_header + full_block


def make_code_header(filename_10: str, length: int, start_addr: int) -> bytes:
    name_bytes = filename_10.encode("latin1", errors="replace")[:10].ljust(10, b" ")
    payload = struct.pack("<B10sHHH", 3, name_bytes, length, start_addr, 0x8000)
    return make_tap_block(0x00, payload)


def make_data_block(payload: bytes) -> bytes:
    return make_tap_block(0xFF, payload)


def extract_ram_from_tap(tap_bytes: bytes) -> bytearray:
    ram = bytearray(65536)
    offset = 0
    cur_start = 0
    while offset + 2 <= len(tap_bytes):
        blen = struct.unpack("<H", tap_bytes[offset:offset + 2])[0]
        offset += 2
        block = tap_bytes[offset:offset + blen]
        offset += blen
        if not block:
            continue
        flag = block[0]
        if flag == 0x00 and len(block) >= 18:
            typ, name, dlen, start, p2 = struct.unpack("<B10sHHH", block[1:18])
            cur_start = start
        elif flag == 0xFF:
            payload = block[1:-1]
            if cur_start + len(payload) <= 65536:
                ram[cur_start:cur_start + len(payload)] = payload
            else:
                avail = max(0, 65536 - cur_start)
                ram[cur_start:65536] = payload[:avail]
            cur_start += len(payload)
    return ram


def load_file_ram(input_path: str) -> bytearray:
    with open(input_path, "rb") as f:
        data = f.read()

    lower = input_path.lower()
    if lower.endswith(".sna"):
        snap = load_sna(data, input_path)
        return snap.ram
    elif lower.endswith(".z80"):
        snap = load_z80(data, input_path)
        return snap.ram
    elif lower.endswith(".tap"):
        return extract_ram_from_tap(data)
    else:
        # Heuristic fallback: check size
        if len(data) == 49179 or len(data) >= 131103:
            return load_sna(data, input_path).ram
        elif len(data) > 30 and data[12] & 0x20:
            return load_z80(data, input_path).ram
        else:
            return extract_ram_from_tap(data)


def export_paws_tap(input_path: str, out_tap_path: str, tape_name: str = ""):
    if not os.path.exists(input_path):
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if not tape_name:
        base = os.path.splitext(os.path.basename(input_path))[0]
        tape_name = base.upper()[:8]

    ram = load_file_ram(input_path)

    # Read authentic PAWS pointers at 0xFFFD, 0xFFED, and 0xFFEF
    val_fffd = ram[0xFFFD] | (ram[0xFFFE] << 8)
    val_ffed = ram[0xFFED] | (ram[0xFFEE] << 8)
    val_ffef = ram[0xFFEF] | (ram[0xFFF0] << 8)
    val_ffd9 = ram[0xFFD9] | (ram[0xFFDA] << 8)

    print(f"[{os.path.basename(input_path)}] PAWS Database Pointers:")
    print(f"  - maintop (0xFFFD): 0x{val_fffd:04X} ({val_fffd})")
    print(f"  - end_a   (0xFFED): 0x{val_ffed:04X} ({val_ffed})")
    print(f"  - start_b (0xFFEF): 0x{val_ffef:04X} ({val_ffef})")
    print(f"  - vocab   (0xFFD9): 0x{val_ffd9:04X} ({val_ffd9})")

    if val_fffd < 0x8000 or val_ffed <= val_fffd or val_ffef < 0x8000 or val_ffef >= 0x10000:
        print(f"Error: Invalid or corrupted PAWS pointers in {input_path}", file=sys.stderr)
        sys.exit(1)

    name_clean = tape_name.strip()[:9].ljust(9, " ")

    # Block A: (0xFFFD) to (0xFFED)
    block_a_data = bytes(ram[val_fffd:val_ffed])
    len_a = len(block_a_data)
    hdr_a = make_code_header(name_clean + "A", len_a, val_fffd)
    dat_a = make_data_block(block_a_data)

    # Block B: (0xFFEF) to 0x10000 (Database part 2 + System Pointers 0xFFD9..0xFFFF)
    block_b_data = bytes(ram[val_ffef:0x10000])
    len_b = len(block_b_data)
    hdr_b = make_code_header(name_clean + "B", len_b, val_ffef)
    dat_b = make_data_block(block_b_data)

    tap_data = hdr_a + dat_a + hdr_b + dat_b
    with open(out_tap_path, "wb") as f:
        f.write(tap_data)

    print(f"  -> Generated: {out_tap_path}")
    print(f"     Block A: '{name_clean}A' start=0x{val_fffd:04X}, len={len_a}")
    print(f"     Block B: '{name_clean}B' start=0x{val_ffef:04X}, len={len_b}")
    print(f"     Total TAP size: {len(tap_data)} bytes\n")


def main():
    if len(sys.argv) < 3:
        print("PAWS Database Tape Exporter (SpeccyLift standalone)")
        print("Usage: python3 export_paws_tap.py <input.sna|input.z80|input.tap> <output.tap> [tape_name]")
        sys.exit(1)
    name = sys.argv[3] if len(sys.argv) > 3 else ""
    export_paws_tap(sys.argv[1], sys.argv[2], name)


if __name__ == "__main__":
    main()
