"""
Build complete font table by OCR-ing all 14 font texture pages using manga-ocr.
Each page is 256x256 pixels with 16x16 grid of 16px characters.
Total: 14 pages × 256 chars = 3584 positions.
"""
import sys
import os
import json
from PIL import Image

FONT_DIR = "DATA/EXPORT_TXD"
PAGES = 14
GRID = 16  # 16x16 grid per page
CELL = 16  # 16x16 pixels per cell
CHARS_PER_PAGE = GRID * GRID  # 256

# First load existing FONT.TXT for verification
def loadFontTxt(path="DATA/FONT.TXT"):
    with open(path, "rb") as f:
        raw = f.read()
    content = raw.decode("shift_jis")
    return [c for c in content if c not in "\n\r"]


def isEmptyCell(img, threshold=10):
    """Check if a cell image is essentially empty (all dark/transparent)."""
    pixels = list(img.getdata())
    if img.mode == "P":
        # Palette mode - check if all pixels are the same (background)
        return len(set(pixels)) <= 2 and max(pixels) < threshold
    elif img.mode in ("RGB", "RGBA"):
        bright = sum(1 for p in pixels if (p[0] + p[1] + p[2]) > 30)
        return bright < 5
    elif img.mode == "L":
        bright = sum(1 for p in pixels if p > 30)
        return bright < 5
    return False


def buildFontTable():
    # Initialize manga-ocr
    print("Loading manga-ocr model...")
    sys.path.insert(0, r"D:\manga-ocr-master")
    from manga_ocr import MangaOcr
    mocr = MangaOcr()
    print("Model loaded.")

    font_table = {}  # index -> char
    
    for page in range(PAGES):
        png_path = os.path.join(FONT_DIR, f"FONT_font_{page:02d}.png")
        if not os.path.exists(png_path):
            print(f"SKIP: {png_path} not found")
            continue
        
        img = Image.open(png_path).convert("RGBA")
        w, h = img.size
        print(f"\nPage {page}: {png_path} ({w}x{h})")
        
        cell_w = w // GRID
        cell_h = h // GRID
        
        page_chars = []
        for row in range(GRID):
            for col in range(GRID):
                idx = page * CHARS_PER_PAGE + row * GRID + col
                x = col * cell_w
                y = row * cell_h
                cell = img.crop((x, y, x + cell_w, y + cell_h))
                
                # Skip empty cells
                cell_gray = cell.convert("L")
                pixels = list(cell_gray.getdata())
                bright_count = sum(1 for p in pixels if p > 30)
                
                if bright_count < 3:
                    page_chars.append("")
                    continue
                
                # Pad the cell image for better OCR (add white border)
                padded = Image.new("RGB", (cell_w * 3, cell_h * 3), (255, 255, 255))
                # Convert cell to RGB with white background
                cell_rgb = Image.new("RGB", cell.size, (255, 255, 255))
                cell_rgb.paste(cell, mask=cell.split()[3] if cell.mode == "RGBA" else None)
                # Invert if needed (white text on dark bg -> black text on white bg)
                from PIL import ImageOps
                cell_inv = ImageOps.invert(cell_rgb)
                padded.paste(cell_inv, (cell_w, cell_h))
                
                try:
                    text = mocr(padded)
                    # manga-ocr may return multiple chars, take first
                    ch = text.strip()
                    if len(ch) > 1:
                        ch = ch[0]  # Take first char only
                    if ch:
                        font_table[idx] = ch
                        page_chars.append(ch)
                    else:
                        page_chars.append("")
                except Exception as e:
                    page_chars.append("")
        
        # Print summary for this page
        filled = sum(1 for c in page_chars if c)
        print(f"  Recognized: {filled}/{CHARS_PER_PAGE}")
        # Show first few
        sample = [(page * CHARS_PER_PAGE + i, c) for i, c in enumerate(page_chars) if c][:20]
        for idx, ch in sample:
            print(f"    [{idx}] = {ch}")
    
    return font_table


def main():
    font_table = buildFontTable()
    
    # Save as JSON
    output_path = "font_table_full.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in sorted(font_table.items())}, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(font_table)} characters to {output_path}")
    
    # Verify against FONT.TXT
    try:
        existing = loadFontTxt()
        matches = 0
        mismatches = 0
        for i, ch in enumerate(existing):
            if i in font_table:
                if font_table[i] == ch:
                    matches += 1
                else:
                    mismatches += 1
                    if mismatches <= 10:
                        print(f"  MISMATCH [{i}]: OCR='{font_table[i]}' vs TXT='{ch}'")
        print(f"\nVerification: {matches} match, {mismatches} mismatch out of {len(existing)} FONT.TXT chars")
    except Exception as e:
        print(f"Could not verify: {e}")


if __name__ == "__main__":
    main()