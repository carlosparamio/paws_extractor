"""
Spectrum Snapshot Parser (.SNA, .Z80, and raw memory dumps)
Self-contained module for ZX Spectrum memory and snapshot analysis.
Supports standard 48K and 128K snapshots.
"""

from dataclasses import dataclass, field
import struct
from typing import Dict, Optional


@dataclass
class CpuState:
    a: int = 0
    f: int = 0
    bc: int = 0
    de: int = 0
    hl: int = 0
    af_prime: int = 0
    bc_prime: int = 0
    de_prime: int = 0
    hl_prime: int = 0
    ix: int = 0
    iy: int = 0
    sp: int = 0
    pc: int = 0
    i: int = 0
    r: int = 0
    im: int = 1
    iff1: bool = True
    iff2: bool = True
    border: int = 7


@dataclass
class SpectrumSnapshot:
    cpu: CpuState = field(default_factory=CpuState)
    ram: bytearray = field(default_factory=lambda: bytearray(65536))
    model: str = "48K"
    source_file: str = ""
    banks: Dict[int, bytearray] = field(default_factory=dict)
    port_7ffd: int = 0

    def read_byte(self, addr: int) -> int:
        return self.ram[addr & 0xFFFF]

    def read_word(self, addr: int) -> int:
        lo = self.ram[addr & 0xFFFF]
        hi = self.ram[(addr + 1) & 0xFFFF]
        return lo | (hi << 8)

    def write_byte(self, addr: int, val: int) -> None:
        self.ram[addr & 0xFFFF] = val & 0xFF

    def write_word(self, addr: int, val: int) -> None:
        self.ram[addr & 0xFFFF] = val & 0xFF
        self.ram[(addr + 1) & 0xFFFF] = (val >> 8) & 0xFF


def load_sna(data: bytes, filename: str = "") -> SpectrumSnapshot:
    """Parses standard 48K or 128K .SNA snapshot."""
    if len(data) < 49179:
        raise ValueError(f"SNA file too short ({len(data)} bytes, expected at least 49179)")

    cpu = CpuState()
    cpu.i = data[0]
    cpu.hl_prime = data[1] | (data[2] << 8)
    cpu.de_prime = data[3] | (data[4] << 8)
    cpu.bc_prime = data[5] | (data[6] << 8)
    cpu.af_prime = data[7] | (data[8] << 8)
    cpu.hl = data[9] | (data[10] << 8)
    cpu.de = data[11] | (data[12] << 8)
    cpu.bc = data[13] | (data[14] << 8)
    cpu.iy = data[15] | (data[16] << 8)
    cpu.ix = data[17] | (data[18] << 8)
    cpu.iff2 = bool(data[19] & 0x04)
    cpu.iff1 = cpu.iff2
    cpu.r = data[20]
    cpu.f = data[21]
    cpu.a = data[22]
    cpu.sp = data[23] | (data[24] << 8)
    cpu.im = data[25]
    cpu.border = data[26] & 0x07

    ram = bytearray(65536)
    banks: Dict[int, bytearray] = {}
    port_7ffd = 0

    # 48K RAM is loaded at 0x4000 - 0xFFFF
    ram[0x4000:0x10000] = data[27:27 + 49152]
    banks[5] = bytearray(data[27:27 + 16384])
    banks[2] = bytearray(data[27 + 16384:27 + 32768])
    banks[0] = bytearray(data[27 + 32768:27 + 49152])

    # In 48K SNA, PC was pushed onto stack before snapshot
    if len(data) == 49179:
        model = "48K"
        sp = cpu.sp
        if 0x4000 <= sp <= 0xFFFE:
            cpu.pc = ram[sp] | (ram[sp + 1] << 8)
            cpu.sp = (sp + 2) & 0xFFFF
        else:
            cpu.pc = 0x8000
    else:
        model = "128K"
        # 128K SNA extension
        ext_offset = 27 + 49152
        if len(data) >= ext_offset + 4:
            cpu.pc = data[ext_offset] | (data[ext_offset + 1] << 8)
            port_7ffd = data[ext_offset + 2]
            paged_bank = port_7ffd & 0x07
            banks[paged_bank] = bytearray(data[27 + 32768:27 + 49152])

            offset = ext_offset + 4
            for b in range(8):
                if b != 5 and b != 2 and b != paged_bank:
                    if offset + 16384 <= len(data):
                        banks[b] = bytearray(data[offset:offset + 16384])
                        offset += 16384

    return SpectrumSnapshot(cpu=cpu, ram=ram, model=model, source_file=filename, banks=banks, port_7ffd=port_7ffd)


def decompress_z80_block(data: bytes) -> bytearray:
    """Decompresses a standard Z80 block using ED ED count val encoding."""
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        if i + 3 < n and data[i] == 0xED and data[i + 1] == 0xED:
            count = data[i + 2]
            val = data[i + 3]
            out.extend([val] * count)
            i += 4
        else:
            out.append(data[i])
            i += 1
    return out


def load_z80(data: bytes, filename: str = "") -> SpectrumSnapshot:
    """Parses .Z80 snapshot (Version 1, 2, or 3)."""
    if len(data) < 30:
        raise ValueError(f"Z80 file too short ({len(data)} bytes)")

    cpu = CpuState()
    cpu.a = data[0]
    cpu.f = data[1]
    cpu.bc = data[2] | (data[3] << 8)
    cpu.hl = data[4] | (data[5] << 8)
    pc = data[6] | (data[7] << 8)
    cpu.sp = data[8] | (data[9] << 8)
    cpu.i = data[10]
    cpu.r = (data[11] & 0x7F) | ((data[12] & 0x01) << 7)

    byte12 = data[12]
    cpu.border = (byte12 >> 1) & 0x07
    is_compressed = bool(byte12 & 0x20)

    cpu.de = data[13] | (data[14] << 8)
    cpu.bc_prime = data[15] | (data[16] << 8)
    cpu.de_prime = data[17] | (data[18] << 8)
    cpu.hl_prime = data[19] | (data[20] << 8)
    cpu.a_prime = data[21]
    cpu.f_prime = data[22]
    cpu.af_prime = (cpu.a_prime << 8) | cpu.f_prime
    cpu.iy = data[23] | (data[24] << 8)
    cpu.ix = data[25] | (data[26] << 8)
    cpu.iff1 = bool(data[27])
    cpu.iff2 = bool(data[28])
    cpu.im = data[29] & 0x03

    ram = bytearray(65536)
    banks: Dict[int, bytearray] = {}
    port_7ffd = 0

    if pc != 0:
        # Version 1 (48K only)
        cpu.pc = pc
        model = "48K"
        payload = data[30:]
        if is_compressed:
            decomp = decompress_z80_block(payload)
            # End marker in v1 is 0x00 0xED 0xED 0x00
            if len(decomp) >= 49152:
                ram[0x4000:0x10000] = decomp[:49152]
            else:
                ram[0x4000:0x4000 + len(decomp)] = decomp
        else:
            ram[0x4000:0x4000 + len(payload)] = payload[:49152]
        banks[5] = bytearray(ram[0x4000:0x8000])
        banks[2] = bytearray(ram[0x8000:0xC000])
        banks[0] = bytearray(ram[0xC000:0x10000])
    else:
        # Version 2 or 3
        ext_len = data[30] | (data[31] << 8)
        header_end = 32 + ext_len
        cpu.pc = data[32] | (data[33] << 8)
        hw_mode = data[34]
        if ext_len >= 4:
            port_7ffd = data[35]

        # Mode detection: in Z80 v2: 3, 4 = 128K; in v3: 4, 5, 6 = 128K / +2
        is_128k = hw_mode in (3, 4, 7, 8) or (ext_len >= 55 and hw_mode in (4, 5, 6))
        model = "128K" if is_128k else "48K"

        # Read pages
        offset = header_end
        while offset + 3 <= len(data):
            block_len = data[offset] | (data[offset + 1] << 8)
            page_id = data[offset + 2]
            offset += 3

            compressed = (block_len != 0xFFFF)
            raw_len = block_len if compressed else 16384
            block_data = data[offset:offset + raw_len]
            offset += raw_len

            page_decomp = decompress_z80_block(block_data) if compressed else block_data

            if is_128k:
                # In 128K mode, Page 3 = Bank 0, Page 4 = Bank 1, ..., Page 10 = Bank 7
                if 3 <= page_id <= 10:
                    bank_num = page_id - 3
                    banks[bank_num] = bytearray(page_decomp[:16384])
            else:
                # In 48K mode: Page 8 = 0x4000 (Bank 5), Page 4 = 0x8000 (Bank 2), Page 5 = 0xC000 (Bank 0)
                if page_id == 8:
                    banks[5] = bytearray(page_decomp[:16384])
                elif page_id == 4:
                    banks[2] = bytearray(page_decomp[:16384])
                elif page_id == 5:
                    banks[0] = bytearray(page_decomp[:16384])

        # Map banks into 64KB RAM
        if 5 in banks:
            ram[0x4000:0x8000] = banks[5]
        if 2 in banks:
            ram[0x8000:0xC000] = banks[2]

        paged_bank = (port_7ffd & 0x07) if is_128k else 0
        if paged_bank in banks:
            ram[0xC000:0x10000] = banks[paged_bank]
        elif 0 in banks:
            ram[0xC000:0x10000] = banks[0]

    return SpectrumSnapshot(cpu=cpu, ram=ram, model=model, source_file=filename, banks=banks, port_7ffd=port_7ffd)
