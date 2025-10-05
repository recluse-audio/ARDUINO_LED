# pixel_array.py
from PIXEL_CLI.pixel import Pixel
from PIXEL_CLI.defaults import (
    DEFAULT_GLOBAL_BRIGHTNESS,
    DEFAULT_RED,
    DEFAULT_GREEN,
    DEFAULT_BLUE,
    load_repo_overrides,
)

# ---------- PixelArray ----------
class PixelArray:
    def __init__(self, led_count: int):
        self.led_count = led_count
        self.pixels = [Pixel(i) for i in range(led_count)]
        self.selected_pixel_index = 0
        self.selected_color: RGB = (DEFAULT_RED, DEFAULT_GREEN, DEFAULT_BLUE)  # <-- selected_color lives here
        self.pixels[0].set_selected(True)
        self.global_brightness = DEFAULT_GLOBAL_BRIGHTNESS

    def set_selected_pixel(self, new_selected_index: int):
        new_selected_index %= self.led_count
        if new_selected_index == self.selected_pixel_index:
            return
        old_px = self.pixels[self.selected_pixel_index]
        old_px.set_selected(False)

        self.selected_pixel_index = new_selected_index
        self.apply_selected_color_to(self.selected_pixel_index)
        self.pixels[self.selected_pixel_index].set_selected(True)

    def get_selected_pixel(self) -> int:
        return self.selected_pixel_index

    def set_global_brightness(self, global_brightness: int):
        self.global_brightness = global_brightness
    
    def get_global_brightness(self) -> int:
        return self.global_brightness

    
    def set_selected_color(self, r: int, g: int, b: int) -> None:
        if r > 255:
            r = 255
        if g > 255:
            g = 255
        if b > 255:
            b = 255

        if r < 0:
            r = 0
        if g < 0:
            g = 0
        if b < 0:
            b = 0

        self.selected_color = (r, g, b)

    def apply_selected_color_to(self, index: int) -> None:
        r, g, b = self.selected_color
        self.set_rgb8(index, r, g, b)

    def set_rgb8(self, led_index: int, r8: int, g8: int, b8: int):
        px = self.pixels[led_index]
        px.set_rgb8(r8, g8, b8)

    def get_rgb8(self, led_index: int):
        return self.pixels[led_index].get_rgb8()

    def get_selected_rgb8(self):
        return self.pixels[selected_pixel_index].get_rgb8()


    def clear(self):
        for px in self.pixels:
            px.is_active = False
            px.r = px.g = px.b = 0
            px.brightness = 0
#------------------------------------