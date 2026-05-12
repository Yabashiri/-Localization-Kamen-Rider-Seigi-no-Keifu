import struct, re

data = open('DATA/MENU/ITEM_MSG.DAT', 'rb').read()

# Header: count of entries
count = struct.unpack_from('<I', data, 0)[0]
print(f'Entry count: {count}')

# Each entry: 2 bytes index, 2 bytes length, 4 bytes offset
entries = []
for i in range(min(count, 10)):
    idx, length, offset = struct.unpack_from('<HHI', data, 4 + i * 8)
    entries.append((idx, length, offset))
    print(f'  Entry {i}: idx={idx}, len={length}, offset=0x{offset:04x}')

# Read font chars
font_chars = open('DATA/FONT.TXT', 'rb').read().decode('shift-jis', errors='replace')
font_chars = [c for c in font_chars if c != '\n' and c != '\r']
print(f'\nFont char count: {len(font_chars)}')
print(f'First 20 chars: {"".join(font_chars[:20])}')

# Try decoding first entry text using font table as lookup
if entries:
    idx0, len0, off0 = entries[0]
    raw = data[off0:off0+len0*2]
    print(f'\nEntry 0 raw bytes: {raw.hex()}')
    decoded = []
    for j in range(0, len(raw), 2):
        code = struct.unpack_from('<H', raw, j)[0]
        if code < len(font_chars):
            decoded.append(font_chars[code])
        else:
            decoded.append(f'[{code}]')
    print(f'Entry 0 decoded: {"".join(decoded)}')

    # Also try entries 1-4
    for ei in range(1, min(5, len(entries))):
        idx_e, len_e, off_e = entries[ei]
        raw_e = data[off_e:off_e+len_e*2]
        decoded_e = []
        for j in range(0, len(raw_e), 2):
            code = struct.unpack_from('<H', raw_e, j)[0]
            if code < len(font_chars):
                decoded_e.append(font_chars[code])
            else:
                decoded_e.append(f'[{code}]')
        print(f'Entry {ei} decoded: {"".join(decoded_e)}')