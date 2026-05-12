import struct

for fname in ["DATA/MENU/CONFIG_MSG.DAT", "DATA/MENU/FIELD_NAME.DAT", "DATA/MENU/ITEM_MSG.DAT"]:
    data = open(fname, "rb").read()
    count = struct.unpack_from("<I", data, 0)[0]
    ds = 4 + count * 8
    print(f"\n{fname}: size={len(data)}, count={count}, data_start=0x{ds:04x}")
    
    # Show first 2 entries
    for i in range(min(count, 2)):
        idx, length, off = struct.unpack_from("<HHI", data, 4 + i * 8)
        print(f"  entry[{i}]: idx={idx}, len={length}, offset=0x{off:04x}")
        
        # Try absolute offset
        if off + length * 2 <= len(data):
            vals = [struct.unpack_from("<H", data, off + j*2)[0] for j in range(min(length, 6))]
            print(f"    absolute: {' '.join(f'{v:04x}' for v in vals)}")
        
        # Try relative offset (from data_start)
        abs2 = ds + off
        if abs2 + length * 2 <= len(data):
            vals = [struct.unpack_from("<H", data, abs2 + j*2)[0] for j in range(min(length, 6))]
            print(f"    relative: {' '.join(f'{v:04x}' for v in vals)}")

# Also check font table
raw = open("DATA/FONT.TXT", "rb").read()
text = raw.decode("shift_jis")
chars = [c for c in text if c not in "\n\r"]
print(f"\nFont table: {len(chars)} chars")
print(f"  [0]={chars[0]} [1]={chars[1]} [10]={chars[10]} [100]={chars[100]}")