#!/usr/bin/env python3
"""
pixel_cli.py  (evdev-based key handling, descriptive names)

Keyboard UI for single-pixel binary protocol:
  - CMD_SET_PIXEL (0x10): [u16 indexLE][u8 R][u8 G][u8 B]
  - CMD_BRIGHTNESS (0x13): [u8 value]
  - CMD_SHOW      (0x04): no payload

Uses Linux evdev for real key DOWN/UP (simultaneous keys & modifiers).
Curses is only used for drawing the UI.

Usage:
  pip install evdev pyserial
  ls -l /dev/input/by-id/*-event-kbd
  python3 pixel_cli.py --port /dev/ttyACM0 --kbd /dev/input/by-id/usb-XXX-event-kbd

Repo-local defaults (no OS-specific paths outside the repo):
  Put a file at:  <repo_root>/config/defaults.toml
  Example:
    port = "/dev/ttyACM0"
    kbd  = "/dev/input/by-id/usb-Raspberry_Pi_Ltd_Pi_500_Keyboard-event-kbd"

If you set those, you can just run:
  PIXEL_CLI
"""

# in src/PIXEL_CLI/pixel_cli.py
from PIXEL_CLI.pixel_array import PixelArray
from PIXEL_CLI.key_state import KeyState, auto_detect_keyboard_device_path
from PIXEL_CLI.pixel_protocol import send_set_pixel, send_brightness, send_show
from PIXEL_CLI.usb_serial import list_candidate_ports,auto_detect_port, open_serial_port, DEFAULT_BAUD_RATE
from PIXEL_CLI.ui import draw_ui
from PIXEL_CLI.defaults import (
    DEFAULT_BAUD_RATE,
    DEFAULT_NUM_LEDS,
    DEFAULT_FPS,
    DEFAULT_STEP,
    FADE_TIME_SECONDS_DEFAULT,
    IS_MONO_DEFAULT,
    load_repo_overrides,
)

import argparse
import time
import sys
import curses
from pathlib import Path
import os



# ---------- repo-local config loading ----------
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    tomllib = None

# src/PIXEL_CLI/pixel_cli.py -> parents[2] == repo root
REPO_CFG = Path(__file__).resolve().parents[2] / "config" / "defaults.toml"


def _read_toml(path: Path) -> dict:
    if tomllib and path.is_file():
        try:
            return tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def load_repo_defaults():
    """
    Load defaults from repo-local config/defaults.toml.
    Returns dict: {'port': str|None, 'kbd': str|None}
    """
    cfg = _read_toml(REPO_CFG)
    port = (cfg.get("port") or "").strip()
    kbd = (cfg.get("kbd") or "").strip()
    return {"port": port or None, "kbd": kbd or None}


#------------ magic numbers to match arduino --------------
_U64_MASK = (1 << 64) - 1

#--------------- evdev keycode names ----------------------
KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN = 'KEY_LEFT', 'KEY_RIGHT', 'KEY_UP', 'KEY_DOWN'
KEY_LEFTSHIFT, KEY_RIGHTSHIFT = 'KEY_LEFTSHIFT', 'KEY_RIGHTSHIFT'
KEY_LEFTCTRL, KEY_RIGHTCTRL   = 'KEY_LEFTCTRL', 'KEY_RIGHTCTRL'
KEY_M, KEY_LEFTBRACE, KEY_RIGHTBRACE = 'KEY_M', 'KEY_LEFTBRACE', 'KEY_RIGHTBRACE'
KEY_C, KEY_F, KEY_SPACE, KEY_Q = 'KEY_C', 'KEY_F', 'KEY_SPACE', 'KEY_Q'
KEY_COMMA, KEY_DOT = 'KEY_COMMA', 'KEY_DOT'
KEY_EQUAL, KEY_MINUS = 'KEY_EQUAL', 'KEY_MINUS'
KEY_KPPLUS, KEY_KPMINUS = 'KEY_KPPLUS', 'KEY_KPMINUS'

# ------------ STATE CONTAINER ------------
from dataclasses import dataclass
@dataclass
class UIState:
    is_mono_mode: bool
    adjustment_step: int       # +/- step
    next_movement_time: float  # monotonic time for next movement repeat
    movement_repeat_interval: float  # base interval
    active_color_index: int # color currently being adjusted

#================================================
#=========== CLEARS ALL PIXELS AND EMPTIES PIXEL ARRAY ===============
def reset_led(serial_port, pixel_array):
    pixel_array.clear()
    for led_index in range(DEFAULT_NUM_LEDS):
        send_set_pixel(serial_port, led_index, 0, 0, 0)
    send_brightness(serial_port, pixel_array.global_brightness)
    send_show(serial_port)
#================================================

#================================================
def fill_led(serial_port, global_brightness, pixel_array, red, green, blue):
    pixel_array.clear()
    for led_index in range(DEFAULT_NUM_LEDS):
        send_set_pixel(serial_port, led_index, red, green, blue)
    send_brightness(serial_port, global_brightness)
    send_show(serial_port)    
#================================================

#================================================
def move_selection(pixel_array, delta_leds: int):
    current_selected_led_index = pixel_array.get_selected_pixel()
    new_selected_led_index = (current_selected_led_index + delta_leds) % DEFAULT_NUM_LEDS
    pixel_array.set_selected_pixel(new_selected_led_index)
#================================================

#=========================================================
#============ POLL KEYBOARD FOR KEYSTROKES ===============
def poll_keyboard(serial_port, key_state: KeyState, pixel_array: PixelArray, current_time:float, ui_state: UIState):
    # Poll keyboard
    key_state.poll()

    # Quit
    if key_state.is_pressed(KEY_LEFTCTRL) and key_state.is_pressed(KEY_C):
        reset_led(serial_port, pixel_array)
        return True

    if key_state.down_edge(KEY_Q):
        reset_led(serial_port, pixel_array)
        return True

    # Mode toggles
    if key_state.down_edge(KEY_M):
        ui_state.is_mono_mode = not ui_state.is_mono_mode
    if key_state.down_edge(KEY_LEFTBRACE):
        ui_state.active_color_index = (ui_state.active_color_index - 1) % 3
    if key_state.down_edge(KEY_RIGHTBRACE):
        ui_state.active_color_index = (ui_state.active_color_index + 1) % 3

    # Fill / Clear
    if key_state.down_edge(KEY_F):
        for led_index in range(DEFAULT_NUM_LEDS):
            r = pixel_array.selected_color[0]
            g = pixel_array.selected_color[1]
            b = pixel_array.selected_color[2]
            fill_led(serial_port, pixel_array.global_brightness, pixel_array, r, g, b)

    if key_state.down_edge(KEY_C):
        pixel_array.clear()
        for led_index in range(DEFAULT_NUM_LEDS):
            send_set_pixel(serial_port, led_index, 0, 0, 0)
        send_show(serial_port)

    # Brightness adjustments (hold-friendly)
    if KEY_COMMA in key_state.pressed_keys:  # dim
        global_brightness = max(0, global_brightness - ui_state.adjustment_step)
        send_brightness(serial_port, global_brightness)
        send_show(serial_port)
    if KEY_DOT in key_state.pressed_keys:    # brighten
        global_brightness = min(255, global_brightness + ui_state.adjustment_step)
        send_brightness(serial_port, global_brightness)
        send_show(serial_port)

    # Space to SHOW
    if key_state.down_edge(KEY_SPACE):
        send_show(serial_port)




    prev_red = pixel_array.selected_color[0]
    prev_green = pixel_array.selected_color[1]
    prev_blue = pixel_array.selected_color[2]

    new_red = prev_red
    new_green = prev_green
    new_blue = prev_blue

    is_increase_pressed = (KEY_EQUAL in key_state.pressed_keys) or (KEY_KPPLUS in key_state.pressed_keys)
    is_decrease_pressed = (KEY_MINUS in key_state.pressed_keys) or (KEY_KPMINUS in key_state.pressed_keys)
    if is_increase_pressed or is_decrease_pressed:
        delta_value = ui_state.adjustment_step if is_increase_pressed else -ui_state.adjustment_step
        if is_mono_mode:
            new_value = max(0, min(255, max(prev_red, prev_green, prev_blue) + delta_value))
            new_red = new_green = new_blue = new_value
        else:
            if ui_state.active_color_index == 0:
                new_red = max(0, min(255, prev_red + delta_value))
            elif ui_state.active_color_index == 1:
                new_green = max(0, min(255, prev_green + delta_value))
            else:
                new_blue = max(0, min(255, prev_blue + delta_value))
        pixel_array.set_selected_color(new_red, new_green, new_blue)

    # Continuous movement while held (with modifiers)
    if current_time >= ui_state.next_movement_time:
        is_shift_down = key_state.is_pressed(KEY_LEFTSHIFT) or key_state.is_pressed(KEY_RIGHTSHIFT)
        is_ctrl_down  = key_state.is_pressed(KEY_LEFTCTRL)  or key_state.is_pressed(KEY_RIGHTCTRL)

        movement_step_multiplier = 1
        if is_shift_down:
            movement_step_multiplier = 3
        if is_ctrl_down:
            movement_step_multiplier = 12

        has_moved = False
        if KEY_LEFT in key_state.pressed_keys:
            move_selection(pixel_array, -movement_step_multiplier)
            has_moved = True
        if KEY_RIGHT in key_state.pressed_keys:
            move_selection(pixel_array, +movement_step_multiplier)
            has_moved = True
        if KEY_UP in key_state.pressed_keys:
            move_selection(pixel_array, +5 * movement_step_multiplier)   # page-ish up
            has_moved = True
        if KEY_DOWN in key_state.pressed_keys:
            move_selection(pixel_array, -9 * movement_step_multiplier)   # page-ish down
            has_moved = True

        if has_moved:
            movement_interval = ui_state.movement_repeat_interval / (2 if is_shift_down else 1)
            movement_interval = movement_interval / (2 if is_ctrl_down else 1)
            ui_state.next_movement_time = current_time + max(0.002, movement_interval)
        else:
            ui_state.next_movement_time = current_time + 0.005  # idle check interval


    return False
#================================================



#================================================
# ---------- Main loop ----------
def run_ui(screen, serial_port, serial_port_name, led_count, ui_refresh_fps, adjustment_step, keyboard_device_path):
    curses.curs_set(0)
    screen.nodelay(True)
    screen.keypad(True)  # still useful for resize handling



    pixel_array = PixelArray(led_count)

    # State for keyboard + UI logic
    ui_state = UIState(
        is_mono_mode=IS_MONO_DEFAULT,
        adjustment_step=adjustment_step,
        next_movement_time=time.time(),
        movement_repeat_interval=1.0 / 60.0,
        active_color_index=0,
    )

    # Initialize device (clear all, set brightness, show)
    reset_led(serial_port, pixel_array)

    draw_ui(
        screen,
        serial_port_name=serial_port_name,
        led_count=led_count,
        ui_refresh_fps=ui_refresh_fps,
        selected_led_index=pixel_array.selected_pixel_index,
        is_mono_mode=ui_state.is_mono_mode,
        active_color_index=ui_state.active_color_index,
        pixel_array=pixel_array,
        global_brightness=pixel_array.global_brightness,
        keyboard_device_path=keyboard_device_path,
    )

    # Timing
    redraw_interval_seconds = 1.0 / max(1, ui_refresh_fps)
    next_redraw_time = time.time()
    last_redraw_time = next_redraw_time


    # evdev keyboard
    key_state = KeyState(keyboard_device_path)

    #===== LOOP =====
    while True:

        current_time = time.time()

        #========= React to keystrokes and perform actions when they occur ======
        should_quit = poll_keyboard(serial_port, key_state, pixel_array, current_time, ui_state)
        if should_quit:
            return


        #========= Redraw command line UI ==============
        if current_time >= next_redraw_time:

            # compute an integer dim step based on elapsed time
            time_since_last_redraw = current_time - last_redraw_time
            last_redraw_time = current_time
            dim_step = max(1, int(255 * time_since_last_redraw / FADE_TIME_SECONDS_DEFAULT))  # ~reach 0 in FADE_TIME_SECONDS_DEFAULT

            any_dirty = False

            for px in pixel_array.pixels:
                pixel_state_before_dim_step = px.get_rgb8()
                px.dim(dim_step)
                pixel_state_after_dim_step = px.get_rgb8()

                if pixel_state_after_dim_step != pixel_state_before_dim_step:
                    send_set_pixel(serial_port, px.index, *pixel_state_after_dim_step)
                    any_dirty = True

            if any_dirty:
                send_show(serial_port)

            draw_ui(
                screen,
                serial_port_name=serial_port_name,
                led_count=DEFAULT_NUM_LEDS,
                ui_refresh_fps=ui_refresh_fps,
                selected_led_index=pixel_array.selected_pixel_index,
                is_mono_mode=ui_state.is_mono_mode,
                active_color_index=ui_state.active_color_index,
                pixel_array=pixel_array,
                global_brightness=pixel_array.global_brightness,
                keyboard_device_path=keyboard_device_path,
            )
            next_redraw_time = current_time + redraw_interval_seconds

        time.sleep(0.001)


def main():
    # Load repo-local defaults first
    defaults = load_repo_defaults()

    argument_parser = argparse.ArgumentParser(
        description="Keyboard UI (evdev) for single-pixel NeoPixel protocol (SET_PIXEL + SHOW + BRIGHTNESS)."
    )
    argument_parser.add_argument("--port", help="Serial port (e.g., /dev/ttyACM0). Defaults to repo config or auto-detect.")
    argument_parser.add_argument("--baud", type=int, default=DEFAULT_BAUD_RATE, help="Baud rate (default 1000000).")
    argument_parser.add_argument("--num-leds", type=int, default=DEFAULT_NUM_LEDS, help="Number of LEDs.")
    argument_parser.add_argument("--fps", type=int, default=50, help="UI redraw rate in frames per second.")
    argument_parser.add_argument("--step", type=int, default=8, help="Value step for +/- edits and brightness.")
    argument_parser.add_argument("--kbd", help="Keyboard event device path (e.g., /dev/input/by-id/usb-XXX-event-kbd). Defaults to repo config or auto-detect.")
    args = argument_parser.parse_args()

    # Resolve serial port + keyboard path using: CLI arg -> repo config -> auto-detect
    serial_port_name = args.port or defaults.get("port") or auto_detect_port()
    if not serial_port_name:
        _, detected_ports_all = list_candidate_ports()
        print("No Arduino serial port auto-detected. Try --port /dev/ttyACM0", file=sys.stderr)
        if detected_ports_all:
            print("Detected ports:", ", ".join(detected_ports_all), file=sys.stderr)
        sys.exit(1)

    keyboard_device_path = args.kbd or defaults.get("kbd") or auto_detect_keyboard_device_path()
    if not keyboard_device_path or not os.path.exists(keyboard_device_path):
        print("No keyboard device found. Provide --kbd /dev/input/by-id/...-event-kbd", file=sys.stderr)
        sys.exit(1)

    try:
        serial_port = open_serial_port(serial_port_name, baud_rate=args.baud, timeout=0.0)
    except Exception as open_error:
        print(f"Failed to open {serial_port_name}: {open_error}", file=sys.stderr)
        sys.exit(2)

    # Drain any greeting
    start_time = time.time()
    while time.time() - start_time < 0.5:
        try:
            if not serial_port.readline():
                break
        except Exception:
            break

    try:
        curses.wrapper(
            run_ui,
            serial_port,
            serial_port_name,
            args.num_leds,
            args.fps,
            args.step,
            keyboard_device_path,
        )
    finally:
        try:
            serial_port.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
