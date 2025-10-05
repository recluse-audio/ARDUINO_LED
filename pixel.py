# pixel.py

_U64_MASK = (1 << 64) - 1

class Pixel:
    """
    Represents a single LED's state.

    Fields:
      - index: LED index (int)
      - is_active: whether this pixel was explicitly set recently (bool)
      - r,g,b: 64-bit channel values (stored as Python ints, masked to uint64)
      - brightness: per-pixel brightness (0..255). Note: device also has a global brightness.
    """
    __slots__ = ("index", "is_active", "is_selected", "r", "g", "b", "brightness")
    def __init__(self, index: int, is_active: bool = False, is_selected: bool = False,
                 r: int = 0, g: int = 0, b: int = 0, brightness: int = 255):
        self.index = int(index)
        self.is_active = bool(is_active)
        self.is_selected = bool(is_selected)
        self.r = r & _U64_MASK
        self.g = g & _U64_MASK
        self.b = b & _U64_MASK
        self.brightness = max(0, min(255, int(brightness)))

    def set_rgb8(self, r8: int, g8: int, b8: int):
        """Set channels from 8-bit values (stored as uint64 internally)."""
        self.r = int(r8) & 0xFF
        self.g = int(g8) & 0xFF
        self.b = int(b8) & 0xFF

    def get_rgb8(self):
        """Return (r,g,b) as 8-bit tuple (lower 8 bits of the 64-bit fields)."""
        return (int(self.r) & 0xFF, int(self.g) & 0xFF, int(self.b) & 0xFF)

    # set this pixel index as selected or not.
    # when selected it's color values do not drop
    def set_selected(self, is_selected: bool):
        self.is_selected = is_selected
        self.brightness = 255

    # dim the pixel by given amount
    def dim(self, amount: int) -> None:
        if self.is_selected:
            return
        if not self.is_active and (self.r == 0 and self.g == 0 and self.b == 0):
            return  # already dark and inactive

        a = 0 if amount is None else max(0, int(amount))
        if a == 0:
            return

        self.r = max(0, self.r - a)
        self.g = max(0, self.g - a)
        self.b = max(0, self.b - a)

        # optionally gate "active" off when fully dark
        if self.r == 0 and self.g == 0 and self.b == 0:
            self.is_active = False
