import struct

data = open('DATA/MENU/HINT.BIN', 'rb').read()
print(f'HINT.BIN size: {len(data)} bytes')
print(f'Header hex (64 bytes):')
for i in range(0, 64, 16):
    hex_part = ' '.join(f'{b:02x}' for b in data[i:i+16])
    print(f'  {i:04x}  {hex_part}')

# Check if it's Shift-JIS text directly
text = data.decode('shift-jis', errors='replace')
# Find readable Japanese strings
import re
matches = re.findall(r'[\u3040-\u9fff\uff00-\uffef\u3000-\u303f]{3,}', text)
print(f'\nReadable Japanese fragments: {len(matches)}')
for m in matches[:15]:
    print(f'  {m}')

# Also check HINT.BIN with font table indexing
font_raw = open('DATA/FONT.TXT', 'rb').read()
font_text = font_raw.decode('shift-jis', errors='replace')
# Keep ALL characters including spaces and newlines
font_chars = list(font_text.replace('\r\n', '').replace('\n', '').replace('\r', ''))
print(f'\nFont table: {len(font_chars)} characters')

# Try first 4 bytes as entry count
count = struct.unpack_from('<I', data, 0)[0]
print(f'First 4 bytes as uint32: {count} (0x{count:08x})')

# Try reading as font-indexed text
decoded = []
for j in range(0, min(100, len(data)), 2):
    code = struct.unpack_from('<H', data, j)[0]
    if code < len(font_chars):
        decoded.append(font_chars[code])
    elif code == 0x8000:
        decoded.append('[EOS]')
    elif code == 0x8100:
        decoded.append('[NL]')
    else:
        decoded.append(f'[{code}]')
print(f'\nAs font indices (first 50 codes): {"".join(decoded)}')