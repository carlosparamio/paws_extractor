# PAWS Database Tape Exporter & Decompilation Utility

A standalone, dependency-free utility to extract authentic adventure database blocks (`Block A` and `Block B`) from compiled ZX Spectrum adventure releases (snapshots `.SNA`, `.Z80`, or tapes `.TAP`) created with Gilsoft's **Professional Adventure Writer (PAWS)**.

The generated `.TAP` file can be loaded directly into PAWS running in any ZX Spectrum emulator (such as ZEsarUX, Fuse, or Spectaculator) via **Option `J` ("Load database" in Extra Options)**.

---

## Background & Memory Architecture

Commercial PAWS games on ZX Spectrum are stored with their active database bounded by system pointers:
- **`0xFFFD` (`maintop`)**: Start of dynamic database (typically `0x9300`).
  - Vocabulary tables and token dictionary
  - Location descriptions
  - Connections / movement tables
  - User and system messages
  - Object records (locations, words, weight, attributes)
  - Process tables (Process 0, 1, 2, 3...)
- **`0xFFED` (`end_a`)**: End of Database Part 1 (`Block A`).
- **Free Memory Gap** (`(0xFFED)..(0xFFEF)`): Left empty for the authoring environment's workspace.
- **`0xFFEF` (`start_b`)**: Start of Database Part 2 (`Block B`), containing system table pointers (`0xFFD9..0xFFFF`).

When saving a database to tape, the authentic PAWS routine (at `0x706E` in Bank 5) writes two standard Sinclair CODE blocks:
1. **`Block A`**: from `(0xFFFD)` to `(0xFFED)` (named `<NAME>    A`).
2. **`Block B`**: from `(0xFFEF)` to `0x10000` (named `<NAME>    B`).

---

## Features

- **Multi-format Support**:
  - ZX Spectrum 48K and 128K snapshots (`.SNA`).
  - ZX Spectrum `.Z80` snapshots (Version 1, 2, and 3, with full 128K multi-page bank support).
  - Standard tape images (`.TAP`).
- **Zero External Dependencies**: Pure Python 3 standard library only.
- **Preserves Memory Integrity**: Computes exact pointer bounds and ensures no overlap into PAWS system variables or token dictionaries.

---

## Usage

```bash
python3 export_paws_tap.py <input_file> <output_tap> [tape_name]
```

### Examples

1. Extract database from a 48K `.SNA` snapshot:
   ```bash
   python3 export_paws_tap.py things.sna things_db.tap
   ```

2. Extract database from a 128K `.Z80` snapshot:
   ```bash
   python3 export_paws_tap.py espia.z80 espia_db.tap ESPIA
   ```

3. Extract database from a commercial release `.TAP`:
   ```bash
   python3 export_paws_tap.py release.tap game_db.tap GAME
   ```

---

## Loading into PAWS

1. Open the original PAWS (48K or 128K) in your emulator.
2. Press Space to enter the Main Menu.
3. Select **`E`** (Extra Options).
4. Insert your generated `<name>_db.tap` file into the emulator's virtual tape drive.
5. Select **`J`** (Load database) and type the adventure name (or press Enter).
6. PAWS will load `Block A` and `Block B` cleanly into memory. All tables (Vocabulary, Locations, Connections, Messages, Objects, and Processes) will be immediately accessible in the PAWS editor and test runner!
