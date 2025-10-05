# image_to_led.py
from PIL import Image, ImageOps
from pixel_cli_ui_v4 import send_set_pixel, send_show  # uses your existing protocol fns

def _map_xy_to_index(x: int, y: int, width: int, height: int,
                     serpentine: bool = False,
                     origin: str = "top_left") -> int:
    # Adjust origin
    if origin.startswith("bottom"):
        y = (height - 1) - y
    if origin.endswith("right"):
        x = (width  - 1) - x
    # Serpentine
    if serpentine and (y % 2 == 1):
        x = (width - 1) - x
    return y * width + x

def load_image_as_16x16_rgb(image_path: str,
                            target_w: int = 16,
                            target_h: int = 16,
                            mode: str = "fit",
                            background=(0, 0, 0)):
    """
    Works for PNG/JPEG/etc. Handles EXIF orientation and alpha, returns list[(R,G,B)].
    mode: 'fit' (letterbox), 'fill' (cover+crop), or 'stretch' (distort).
    """
    im = Image.open(image_path)
    im = ImageOps.exif_transpose(im)          # fix camera rotation
    im = im.convert("RGBA")                   # unify (alpha-friendly)

    if mode == "fit":
        canvas = Image.new("RGBA", (target_w, target_h), (*background, 255))
        im.thumbnail((target_w, target_h), Image.LANCZOS)
        x = (target_w - im.width) // 2
        y = (target_h - im.height) // 2
        canvas.paste(im, (x, y), im)
        out = canvas
    elif mode == "fill":
        sw, sh = im.size
        scale = max(target_w / sw, target_h / sh)
        im2 = im.resize((max(1, int(round(sw * scale))),
                         max(1, int(round(sh * scale)))), Image.LANCZOS)
        left = (im2.width - target_w) // 2
        top  = (im2.height - target_h) // 2
        out = im2.crop((left, top, left + target_w, top + target_h))
    elif mode == "stretch":
        out = im.resize((target_w, target_h), Image.BILINEAR)
    else:
        raise ValueError("mode must be 'fit', 'fill', or 'stretch'")

    rgb = Image.new("RGB", out.size, background)
    rgb.paste(out, mask=out.split()[-1])  # alpha composite
    return list(rgb.getdata())

def push_image_to_leds(image_path: str,
                       serial_port,
                       grid_w: int = 16,
                       grid_h: int = 16,
                       serpentine: bool = False,
                       origin: str = "top_left",
                       mode: str = "fit",
                       background=(0, 0, 0),
                       gamma: float = 1.0):
    """
    Downsample and send the image to the LED grid using SET_PIXEL/SHOW.
    """
    rgb = load_image_as_16x16_rgb(
        image_path, target_w=grid_w, target_h=grid_h, mode=mode, background=background
    )

    # Optional gamma correction
    if gamma and gamma != 1.0:
        inv = 1.0 / gamma
        lut = [int(round((i / 255.0) ** inv * 255.0)) for i in range(256)]
        rgb = [(lut[r], lut[g], lut[b]) for (r, g, b) in rgb]

    # Send pixels (one SHOW at the end)
    for y in range(grid_h):
        for x in range(grid_w):
            r, g, b = rgb[y * grid_w + x]
            idx = _map_xy_to_index(x, y, grid_w, grid_h, serpentine=serpentine, origin=origin)
            send_set_pixel(serial_port, idx, r, g, b)

    send_show(serial_port)
