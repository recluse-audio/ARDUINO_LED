#!/usr/bin/env python3
# export_font_16x16.py
import argparse
import os
import string
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageColor

# ---------- Character sets ----------
CHARSETS = {
    "ascii_printable": "".join(chr(i) for i in range(32, 127)),   # space..~
    "upper": string.ascii_uppercase,
    "lower": string.ascii_lowercase,
    "digits": string.digits,
    "hex": string.digits + "ABCDEF",
    "alnum": string.ascii_letters + string.digits,
    "basic": string.ascii_uppercase + string.digits,              # handy for LED
}

# ---------- Pillow compatibility helpers ----------
def load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    # Works across Pillow versions (avoid layout_engine arg)
    return ImageFont.truetype(font_path, size=size)

def glyph_bbox(font: ImageFont.FreeTypeFont, ch: str):
    # Prefer FreeTypeFont.getbbox if available; fallback to draw.textbbox
    try:
        return font.getbbox(ch)
    except AttributeError:
        tmp = Image.new("L", (128, 128), 0)
        d = ImageDraw.Draw(tmp)
        return d.textbbox((0, 0), ch, font=font)

# ---------- Sizing ----------
def best_fit_font_size(font_path, box_w, box_h, margin, charset, min_size=6, max_size=64):
    """
    Binary-search a font size that fits *most* glyphs in the box with margin.
    We allow rare overflows to be re-centered/cropped inside 16x16.
    """
    def fits(size):
        font = load_font(font_path, size)
        max_w = max_h = 0
        for ch in charset:
            bbox = glyph_bbox(font, ch)
            if bbox is None:
                continue
            x0, y0, x1, y1 = bbox
            w = x1 - x0
            h = y1 - y0
            if w > max_w: max_w = w
            if h > max_h: max_h = h
        return (max_w + 2*margin) <= box_w and (max_h + 2*margin) <= box_h

    lo, hi = min_size, max_size
    best = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        if fits(mid):
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best

# ---------- Rendering ----------
def render_char_16(font_path, ch, size, box_w=16, box_h=16, margin=1,
                   fg=(255, 255, 255, 255), bg=(0, 0, 0, 0),
                   snap_bitmap=False, vertical_center=True):
    """
    Render a single character into a 16x16 RGBA image.
    - snap_bitmap: convert to 1-bit style for crisp pixels.
    - vertical_center: center within the box (vs baseline-ish).
    """
    font = load_font(font_path, size)

    # Measure ink bbox at origin
    bbox = glyph_bbox(font, ch)
    if bbox is None:
        return Image.new("RGBA", (box_w, box_h), bg)
    x0, y0, x1, y1 = bbox
    ink_w, ink_h = max(1, x1 - x0), max(1, y1 - y0)

    # Draw tight glyph
    glyph_img = Image.new("RGBA", (ink_w, ink_h), (0, 0, 0, 0))
    glyph_draw = ImageDraw.Draw(glyph_img)
    glyph_draw.text((-x0, -y0), ch, font=font, fill=fg)

    # Compose into box
    out = Image.new("RGBA", (box_w, box_h), bg)
    tx = max(margin, (box_w - ink_w) // 2)
    if vertical_center:
        ty = max(margin, (box_h - ink_h) // 2)
    else:
        ascent, descent = font.getmetrics()
        baseline_y = margin + ascent
        ty = baseline_y - ink_h
        ty = max(margin, min(ty, box_h - ink_h - margin))
    out.alpha_composite(glyph_img, (tx, ty))

    if snap_bitmap:
        # Threshold luminance to make 1-bit-looking glyphs on transparent BG
        comp = Image.new("RGBA", out.size, (0, 0, 0, 0))
        comp.alpha_composite(out)
        gray = comp.convert("L")
        bw = gray.point(lambda v: 255 if v >= 128 else 0, mode="L")
        mask = bw
        solid_fg = Image.new("RGBA", out.size, fg)
        clear = Image.new("RGBA", out.size, (0, 0, 0, 0))
        out = Image.composite(solid_fg, clear, mask)

    return out

# ---------- Export ----------
def export_charset(font_path, out_dir, charset, box=16, margin=1,
                   color="#FFFFFF", background="transparent",
                   snap_bitmap=False, pad_names=False):
    os.makedirs(out_dir, exist_ok=True)

    fg = ImageColor.getrgb(color) + (255,)
    bg = (0, 0, 0, 0) if background == "transparent" else (ImageColor.getrgb(background) + (255,))

    size = best_fit_font_size(font_path, box, box, margin, charset)

    for ch in charset:
        fname = char_to_filename(ch, pad_names=pad_names)
        img = render_char_16(font_path, ch, size=size, box_w=box, box_h=box,
                             margin=margin, fg=fg, bg=bg, snap_bitmap=snap_bitmap)
        img.save(os.path.join(out_dir, f"{fname}.png"))

    preview = preview_sheet(out_dir, charset, box)
    preview.save(os.path.join(out_dir, "_preview.png"))
    print(f"Exported {len(charset)} glyphs to {out_dir} (size={size}, box={box}x{box}, margin={margin})")

def preview_sheet(out_dir, charset, box=16, cols=16):
    imgs = []
    for ch in charset:
        fname = char_to_filename(ch)
        path = os.path.join(out_dir, f"{fname}.png")
        imgs.append(Image.open(path).convert("RGBA"))
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * box, rows * box), (0, 0, 0, 0))
    for i, im in enumerate(imgs):
        x = (i % cols) * box
        y = (i // cols) * box
        sheet.alpha_composite(im, (x, y))
    return sheet

def char_to_filename(ch, pad_names=False):
    if ch == " ":
        name = "space"
    elif ch == "\t":
        name = "tab"
    elif ch == "\n":
        name = "newline"
    else:
        code = ord(ch)
        printable = ch if (32 <= code < 127 and ch not in r'\/:*?"<>|') else None
        name = printable if printable else f"U+{code:04X}"
    return name if not pad_names else f"{name:>3}"

# ---------- CLI ----------
def parse_args():
    p = argparse.ArgumentParser(description="Export each glyph as a 16x16 PNG.")
    p.add_argument("--font", required=True, help="Path to .ttf/.otf")
    p.add_argument("--out", default="font_16x16", help="Output directory")
    p.add_argument("--set", default="basic", choices=CHARSETS.keys(),
                   help="Character set to export")
    p.add_argument("--chars", default="", help="Explicit characters (overrides --set)")
    p.add_argument("--box", type=int, default=16, help="Box size (width=height)")
    p.add_argument("--margin", type=int, default=1, help="Inner padding in pixels")
    p.add_argument("--color", default="#FFFFFF", help="Glyph color (e.g. #FFFFFF)")
    p.add_argument("--background", default="transparent", help="'transparent' or a color")
    p.add_argument("--bitmap", action="store_true", help="Snap to 1-bit look (crisp pixels)")
    p.add_argument("--pad-names", action="store_true", help="Pad filenames (visual ordering)")
    return p.parse_args()

def main():
    args = parse_args()
    charset = args.chars if args.chars else CHARSETS[args.set]
    export_charset(
        font_path=args.font,
        out_dir=args.out,
        charset=charset,
        box=args.box,
        margin=args.margin,
        color=args.color,
        background=args.background,
        snap_bitmap=args.bitmap,
        pad_names=args.pad_names,
    )

if __name__ == "__main__":
    main()
