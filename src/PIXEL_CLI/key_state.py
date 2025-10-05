# key_state.py
from evdev import InputDevice, categorize, ecodes
import select

class KeyState:
    """
    Tracks pressed keys by evdev keycode strings (e.g., 'KEY_LEFTSHIFT','KEY_A','KEY_LEFT').
    Provides helpers for combos and edge-triggered actions.
    """
    def __init__(self, device_path: str, *, grab: bool = False):
        self.device = InputDevice(device_path)
        # Non-blocking so reads won't hang if select isn't used or device is quiet.
        try:
            self.device.set_nonblocking(True)
        except Exception:
            pass

        # optional: grab to prevent keys from affecting the shell
        if grab:
            try:
                self.device.grab()
            except Exception:
                # Lack of permissions or console environment—just continue.
                pass

        self.pressed_keys = set()
        self.keys_pressed_this_tick = set()   # keys that went DOWN this poll
        self.keys_released_this_tick = set()  # keys that went UP this poll

    def poll(self):
        """Non-blocking; update sets from any pending events."""
        self.keys_pressed_this_tick.clear()
        self.keys_released_this_tick.clear()

        # Use select to see if the device is readable right now.
        try:
            readable, _, _ = select.select([self.device], [], [], 0)
        except Exception:
            # Device may have been unplugged; leave state as-is.
            return

        if not readable:
            return

        try:
            for input_event in self.device.read():
                if input_event.type != ecodes.EV_KEY:
                    continue

                cat = categorize(input_event)  # has .keycode and .keystate
                # .keycode may be a string or a list of aliases; pick first if list.
                keycode_name = cat.keycode if isinstance(cat.keycode, str) else cat.keycode[0]

                # keystate: 0=UP, 1=DOWN, 2=HOLD/auto-repeat
                if cat.keystate in (1, 2):
                    if keycode_name not in self.pressed_keys:
                        self.keys_pressed_this_tick.add(keycode_name)
                    self.pressed_keys.add(keycode_name)
                elif cat.keystate == 0:
                    if keycode_name in self.pressed_keys:
                        self.pressed_keys.remove(keycode_name)
                        self.keys_released_this_tick.add(keycode_name)
        except (BlockingIOError, OSError):
            # No events or device hiccup; ignore this tick.
            pass

    def is_pressed(self, *keycode_names):
        """Return True if all given keycodes are currently pressed."""
        return all(key_name in self.pressed_keys for key_name in keycode_names)

    def down_edge(self, *keycode_names):
        """Edge-triggered: True if ALL keys went down this tick (useful for toggles)."""
        return all(key_name in self.keys_pressed_this_tick for key_name in keycode_names)
