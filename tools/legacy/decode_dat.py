"""
Decoder/Encoder for Kamen Rider DAT text files.
Format: header(u32 count) + entries(idx:u16, len:u16, offset:u32) + string data (u16 LE font indices)
"""
import struct
import json
import sys
import os

FONT_PATH = "DATA/FONT.TXT"
CONTROL_END = 0x8000
CONTROL_NEWLINE = 0x8100

DAT_FILES = [
    "DATA/MENU/CONFIG_MSG.DAT",
    "DATA/MENU/FIELD_NAME.DAT",
    "DATA/MENU/ITEM_MSG.DAT",
    "DATA/MENU/ITEM_GET_MSG.DAT",
]


def loadFontTable(path=FONT_PATH):
    with open(path, "rb") as f:
        raw = f.read()
    content = raw.decode("shift_jis")
    return [c for c in content if c not in "\n\r"]


def decodeDatFile(datPath, fontTable):
    """Decode a DAT file into a list of {idx, text} entries."""
    with open(datPath, "rb") as f:
        data = f.read()

    count = struct.unpack_from("<I", data, 0)[0]
    dataStart = 4 + count * 8

    entries = []
    for i in range(count):
        off = 4 + i * 8
        idx, length, strOffset = struct.unpack_from("<HHI", data, off)

        chars = []
        pos = strOffset
        for _ in range(length):
            if pos + 2 > len(data):
                break
            val = struct.unpack_from("<H", data, pos)[0]
            pos += 2
            if val == CONTROL_END:
                break
            elif val == CONTROL_NEWLINE:
                chars.append("\n")
            elif val < len(fontTable):
                chars.append(fontTable[val])
            else:
                chars.append(f"[0x{val:04x}]")

        entries.append({"idx": idx, "text": "".join(chars)})

    return entries


def encodeDatFile(entries, fontTable):
    """Encode a list of {idx, text} entries back into DAT binary format."""
    charToIndex = {}
    for i, c in enumerate(fontTable):
        if c not in charToIndex:
            charToIndex[c] = i

    count = len(entries)
    dataStart = 4 + count * 8

    stringData = bytearray()
    entryTable = bytearray()

    for entry in entries:
        idx = entry["idx"]
        text = entry["text"]
        strOffset = dataStart + len(stringData)

        codes = []
        for ch in text:
            if ch == "\n":
                codes.append(CONTROL_NEWLINE)
            elif ch in charToIndex:
                codes.append(charToIndex[ch])
            else:
                raise ValueError(
                    f"Character '{ch}' (U+{ord(ch):04X}) not in font table"
                )
        codes.append(CONTROL_END)

        charCount = len(codes)
        for code in codes:
            stringData += struct.pack("<H", code)

        entryTable += struct.pack("<HHI", idx, charCount, strOffset)

    result = struct.pack("<I", count) + bytes(entryTable) + bytes(stringData)
    return result


def decodeDatToJson(datPath, fontTable, outputPath=None):
    """Decode DAT file and save as JSON."""
    entries = decodeDatFile(datPath, fontTable)
    if outputPath is None:
        outputPath = os.path.splitext(datPath)[0] + ".json"

    with open(outputPath, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    return entries, outputPath


def encodeJsonToDat(jsonPath, fontTable, outputPath=None):
    """Encode JSON back to DAT file."""
    with open(jsonPath, "r", encoding="utf-8") as f:
        entries = json.load(f)

    if outputPath is None:
        outputPath = os.path.splitext(jsonPath)[0] + ".DAT"

    data = encodeDatFile(entries, fontTable)
    with open(outputPath, "wb") as f:
        f.write(data)

    return outputPath


def main():
    fontTable = loadFontTable()
    print(f"Font table: {len(fontTable)} characters")

    if len(sys.argv) > 1 and sys.argv[1] == "encode":
        # Encode mode: JSON -> DAT
        jsonFiles = sys.argv[2:] if len(sys.argv) > 2 else []
        if not jsonFiles:
            print("Usage: decode_dat.py encode <file.json> [...]")
            return
        for jp in jsonFiles:
            outPath = encodeJsonToDat(jp, fontTable)
            print(f"Encoded: {jp} -> {outPath}")
    else:
        # Decode mode: DAT -> JSON
        datFiles = sys.argv[1:] if len(sys.argv) > 1 else DAT_FILES
        for datPath in datFiles:
            if not os.path.exists(datPath):
                print(f"SKIP: {datPath} not found")
                continue
            entries, outPath = decodeDatToJson(datPath, fontTable)
            print(f"\n=== {datPath} ({len(entries)} entries) -> {outPath} ===")
            for e in entries[:5]:
                text = e["text"].replace("\n", "\\n")
                print(f'  [{e["idx"]:3d}] "{text}"')
            if len(entries) > 5:
                print(f"  ... ({len(entries) - 5} more)")

    # Round-trip verification
    if len(sys.argv) <= 1:
        print("\n--- Round-trip verification ---")
        for datPath in DAT_FILES:
            if not os.path.exists(datPath):
                continue
            original = open(datPath, "rb").read()
            entries = decodeDatFile(datPath, fontTable)
            reencoded = encodeDatFile(entries, fontTable)
            if original == reencoded:
                print(f"  OK: {datPath}")
            else:
                print(f"  MISMATCH: {datPath} (orig={len(original)}, new={len(reencoded)})")


if __name__ == "__main__":
    main()