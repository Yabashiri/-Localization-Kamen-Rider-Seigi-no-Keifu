"""Diagnose Kamen Rider font-code mapping hypotheses.

The old decoder assumes DAT u16 values are dense indices into DATA/FONT.TXT.
This script compares that against atlas-based mappings made from exported
FONT_font_XX.png pages and DATA/EXPORT_TXD/FONT_data.json.
"""
import json
import os
import re
import struct
from collections import Counter

from PIL import Image


FONT_TXT = "DATA/FONT.TXT"
FONT_JSON = "DATA/EXPORT_TXD/FONT_data.json"
FONT_DIR = "DATA/EXPORT_TXD"
CELL = 16
GRID = 16
PAGES = 14

CONTROL = {
    0x8000: "{END}",
    0x8100: "\n",
}


def load_font_txt():
    raw = open(FONT_TXT, "rb").read()
    text = raw.decode("shift_jis", errors="replace")
    return [c for c in text if c not in "\r\n"]


def load_font_json_rows():
    with open(FONT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def cell_nonzero_count(img, page, row, col):
    crop = img.crop((col * CELL, row * CELL, (col + 1) * CELL, (row + 1) * CELL))
    vals = list(crop.getdata())
    # In these paletted PNGs, palette index 0 behaves like transparent/background.
    return sum(1 for v in vals if v != 0)


def atlas_nonempty_slots(threshold=2):
    slots = []
    per_page = []
    for page in range(PAGES):
        path = os.path.join(FONT_DIR, f"FONT_font_{page:02d}.png")
        img = Image.open(path)
        count = 0
        for row in range(GRID):
            for col in range(GRID):
                code = page * 0x100 + row * 0x10 + col
                if cell_nonzero_count(img, page, row, col) > threshold:
                    slots.append(code)
                    count += 1
        per_page.append(count)
    return slots, per_page


def map_dense_txt(font_chars):
    return {i: ch for i, ch in enumerate(font_chars)}


def map_sparse_txt(font_chars, slots):
    return {code: ch for code, ch in zip(slots, font_chars)}


def map_json_linear(data):
    """FONT_data rows appear to be 9 glyphs/row, but assign them densely."""
    m = {}
    idx = 0
    for page in range(PAGES):
        rows = data.get(f"FONT_font_{page:02d}", [])
        for row in rows:
            for ch in row:
                m[idx] = ch
                idx += 1
    return m


def map_json_by_9col(data):
    """Assign FONT_data.json entries as page*0x100 + row*0x10 + col.

    The JSON has 9 visible columns per row, likely because exporter cropped only
    the used area. This tests whether those are left-aligned in 16x16 pages.
    """
    m = {}
    for page in range(PAGES):
        rows = data.get(f"FONT_font_{page:02d}", [])
        for row_i, row in enumerate(rows):
            for col_i, ch in enumerate(row):
                m[page * 0x100 + row_i * 0x10 + col_i] = ch
    return m


def map_json_by_9wide_pages(data):
    """Assign JSON as page base + sequential slots in a 9-column virtual grid.

    Code = page*0x100 + local sequential index. This matches the visual fact
    that FONT_data.json has 9 chars per row, but DAT values may still be page-local.
    """
    m = {}
    for page in range(PAGES):
        idx = 0
        rows = data.get(f"FONT_font_{page:02d}", [])
        for row in rows:
            for ch in row:
                m[page * 0x100 + idx] = ch
                idx += 1
    return m


def map_hybrid_page0_dense_then_json(data, font_chars):
    """Best current hypothesis.

    Codes 0x0000..0x00ff are direct page-0 glyph indices. Later pages are
    stored as page*0x100 + local_index, where FONT_data.json lists only the
    used glyphs on that page in order. This fixes the old dense FONT.TXT shift
    and matches sample menu/scenario text.
    """
    m = {i: ch for i, ch in enumerate(font_chars[:0x100])}
    for page in range(1, PAGES):
        idx = 0
        rows = data.get(f"FONT_font_{page:02d}", [])
        for row in rows:
            for ch in row:
                m[page * 0x100 + idx] = ch
                idx += 1
    return m


def find_dat_like_files(root="DATA"):
    paths = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if not fn.lower().endswith((".dat", ".bin")):
                continue
            path = os.path.join(dirpath, fn)
            try:
                data = open(path, "rb").read()
                if len(data) < 12:
                    continue
                count = struct.unpack_from("<I", data, 0)[0]
                if not (0 < count < 10000 and 4 + count * 8 <= len(data)):
                    continue
                valid = 0
                for i in range(min(count, 20)):
                    _, length, off = struct.unpack_from("<HHI", data, 4 + i * 8)
                    if off < len(data) and off + length * 2 <= len(data):
                        valid += 1
                if valid >= max(1, min(count, 20) // 2):
                    paths.append(path)
            except Exception:
                pass
    return sorted(paths)


def read_dat_entries(path):
    data = open(path, "rb").read()
    count = struct.unpack_from("<I", data, 0)[0]
    entries = []
    for i in range(count):
        idx, length, off = struct.unpack_from("<HHI", data, 4 + i * 8)
        codes = []
        for j in range(length):
            pos = off + j * 2
            if pos + 2 > len(data):
                break
            codes.append(struct.unpack_from("<H", data, pos)[0])
        entries.append((idx, codes))
    return entries


def decode_codes(codes, fmap):
    out = []
    unknown = 0
    for code in codes:
        if code in CONTROL:
            out.append(CONTROL[code])
        elif code in fmap:
            out.append(fmap[code])
        else:
            out.append(f"[{code:04X}]")
            unknown += 1
    return "".join(out), unknown


def score_text(s):
    # Rough readability score: known kana/kanji/fullwidth/ASCII minus unknown tokens.
    unknown = len(re.findall(r"\[[0-9A-F]{4}\]", s))
    jp = len(re.findall(r"[\u3040-\u30ff\u3400-\u9fff\uff00-\uffef]", s))
    controls = s.count("{END}") + s.count("\n")
    return jp + controls * 2 - unknown * 10


def collect_used_codes(paths):
    used = Counter()
    control = Counter()
    for path in paths:
        for _, codes in read_dat_entries(path):
            for c in codes:
                if c >= 0x8000:
                    control[c] += 1
                else:
                    used[c] += 1
    return used, control


def main():
    font_chars = load_font_txt()
    font_json = load_font_json_rows()
    slots, per_page = atlas_nonempty_slots()
    print(f"FONT.TXT chars: {len(font_chars)}")
    print(f"Atlas nonempty slots: {len(slots)} per page={per_page}")
    print(f"First/last nonempty slots: 0x{slots[0]:04X} .. 0x{slots[-1]:04X}")

    maps = {
        "dense_txt_old": map_dense_txt(font_chars),
        "sparse_txt_nonempty_atlas": map_sparse_txt(font_chars, slots),
        "json_linear": map_json_linear(font_json),
        "json_by_9col_left": map_json_by_9col(font_json),
        "json_by_9wide_pages": map_json_by_9wide_pages(font_json),
        "hybrid_page0_dense_then_json": map_hybrid_page0_dense_then_json(font_json, font_chars),
    }

    sample_paths = [
        "DATA/MENU/ITEM_MSG.DAT",
        "DATA/MENU/CONFIG_MSG.DAT",
        "DATA/MENU/FIELD_NAME.DAT",
        "DATA/MENU/STATUS_MSG.DAT",
        "DATA/SCREVENT/MSG/EV001.DAT",
        "DATA/SCREVENT/MSG/H_FILE.DAT",
        "DATA/SCREVENT/MSG/DOOR_CLOSE.DAT",
        "DATA/SCREVENT/MSG/R01A.DAT",
    ]
    sample_paths = [p for p in sample_paths if os.path.exists(p)]

    used, controls = collect_used_codes(sample_paths)
    print(f"\nSample DAT files: {len(sample_paths)}")
    print(f"Used glyph codes: {len(used)}, min=0x{min(used):04X}, max=0x{max(used):04X}")
    print("Control/high codes:", ", ".join(f"0x{k:04X}:{v}" for k, v in controls.most_common()))

    for name, fmap in maps.items():
        missing = sum(cnt for code, cnt in used.items() if code not in fmap)
        covered = sum(cnt for code, cnt in used.items() if code in fmap)
        print(f"\n=== MAP {name} entries={len(fmap)} covered={covered} missing={missing} ===")
        total_score = 0
        for path in sample_paths[:4]:
            entries = read_dat_entries(path)
            print(f"-- {path}")
            for idx, codes in entries[:3]:
                text, unk = decode_codes(codes, fmap)
                total_score += score_text(text)
                shown = text.replace("\n", "\\n")
                if len(shown) > 120:
                    shown = shown[:117] + "..."
                raw = " ".join(f"{c:04X}" for c in codes[:12])
                print(f"  [{idx}] unk={unk:2d} raw={raw} :: {shown}")
        print(f"score={total_score}")

    best = maps["hybrid_page0_dense_then_json"]
    all_paths = find_dat_like_files("DATA")
    all_used, all_controls = collect_used_codes(all_paths)
    missing_codes = Counter({code: cnt for code, cnt in all_used.items() if code not in best})
    print("\n=== FULL DAT-LIKE AUDIT with hybrid_page0_dense_then_json ===")
    print(f"DAT-like files: {len(all_paths)}")
    print(f"Used glyph codes: {len(all_used)}, min=0x{min(all_used):04X}, max=0x{max(all_used):04X}")
    print("Control/high codes:", ", ".join(f"0x{k:04X}:{v}" for k, v in all_controls.most_common(20)))
    print(f"Missing unique codes: {len(missing_codes)}, occurrences: {sum(missing_codes.values())}")
    if missing_codes:
        print("Top missing:", ", ".join(f"0x{k:04X}:{v}" for k, v in missing_codes.most_common(30)))

    print("\nSample scenario decode using best map:")
    for path in ["DATA/SCREVENT/MSG/EV001.DAT", "DATA/SCREVENT/MSG/DOOR_CLOSE.DAT", "DATA/SCREVENT/MSG/R01A.DAT"]:
        if not os.path.exists(path):
            continue
        print(f"-- {path}")
        for idx, codes in read_dat_entries(path)[:5]:
            text, unk = decode_codes(codes, best)
            shown = text.replace("\n", "\\n")
            print(f"  [{idx}] unk={unk}: {shown}")


if __name__ == "__main__":
    main()