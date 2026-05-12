"""Dump a single DAT file with full details."""
import struct
import sys

FONT_PATH = "DATA/FONT.TXT"
CONTROL_END = 0x8000
CONTROL_NEWLINE = 0x8100


def loadFontTable(path=FONT_PATH):
    with open(path, "rb") as f:
        raw = f.read()
    content = raw.decode("shift_jis")
    return [c for c in content if c not in "\n\r"]


def dumpDat(datPath, fontTable):
    with open(datPath, "rb") as f:
        data = f.read()

    count = struct.unpack_from("<I", data, 0)[0]
    dataStart = 4 + count * 8
    print(f"File: {datPath}")
    print(f"Size: {len(data)} bytes, count: {count}, data_start: 0x{dataStart:04x}")
    print()

    for i in range(count):
        off = 4 + i * 8
        idx, length, strOffset = struct.unpack_from("<HHI", data, off)

        # Read raw u16 values
        codes = []
        pos = strOffset
        for _ in range(length):
            if pos + 2 > len(data):
                break
            val = struct.unpack_from("<H", data, pos)[0]
            codes.append(val)
            pos += 2

        # Decode to text
        chars = []
        for val in codes:
            if val == CONTROL_END:
                chars.append("{END}")
            elif val == CONTROL_NEWLINE:
                chars.append("{NL}")
            elif val < len(fontTable):
                chars.append(fontTable[val])
            else:
                chars.append(f"{{0x{val:04x}}}")

        text = "".join(chars)
        raw_hex = " ".join(f"{c:04x}" for c in codes[:20])
        if len(codes) > 20:
            raw_hex += " ..."

        print(f"  [{idx:3d}] off=0x{strOffset:04x} len={length}")
        print(f"         raw: {raw_hex}")
        print(f"         txt: {text}")
        print()


if __name__ == "__main__":
    fontTable = loadFontTable()
    print(f"Font table: {len(fontTable)} chars\n")

    path = sys.argv[1] if len(sys.argv) > 1 else "DATA/MENU/CONFIG_MSG.DAT"
    dumpDat(path, fontTable)