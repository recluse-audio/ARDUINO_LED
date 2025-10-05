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
"""

from pixel_array import PixelArray
from key_state import KeyState
from pixel_protocol import (send_set_pixel,send_brightness,send_show,)

import argparse
import time
import sys
import curses
import serial
from serial.tools import list_ports

# ---- evdev for real key up/down ----
from evdev import InputDevice, categorize, ecodes
import select
import os
import glob
from dataclasses import dataclass


#------------ magic numbers to match arduino --------------
DEFAULT_BAUD_RATE = 1_000_000
_U64_MASK = (1 << 64) - 1

# ------------ DEFAULTS ------------------
FADE_TIME_SECONDS_DEFAULT = 1.0 # how long it will take to fade to darkness
IS_MONO_DEFAULT = False
    


# ---------- Serial helpers ----------
def list_candidate_ports():
    candidate_devices, all_ports = [], []
    for port_info in list_ports.comports():
        all_ports.append(port_info.device)
        device_name = (port_info.device or "").lower()
        description = (port_info.description or "").lower()
        if "ttyacm" in device_name or "arduino" in description or "wch" in description or "ch340" in description or "usb serial" in description:
            candidate_devices.append(port_info.device)
    return candidate_devices, all_ports

def auto_detect_port():
    candidate_devices, _ = list_candidate_ports()
    return candidate_devices[0] if candidate_devices else None

def open_serial_port(port_path, baud_rate=DEFAULT_BAUD_RATE, timeout=0.0):
    serial_port = serial.Serial(port_path, baudrate=baud_rate, timeout=timeout)
    time.sleep(2.0)  # allow board to reset
    serial_port.reset_input_buffer()
    return serial_port


# ---------- evdev input ----------
def auto_detect_keyboard_device_path():
    # Prefer stable by-id paths that end with -event-kbd
    by_id_keyboard_paths = glob.glob("/dev/input/by-id/*-event-kbd")
    if by_id_keyboard_paths:
        return by_id_keyboard_paths[0]
    # Fallback: first event device that reports EV_KEY (not ideal)
    event_device_paths = glob.glob("/dev/input/event*")
    return event_device_paths[0] if event_device_paths else None

# ---------- UI help ----------
HELP_LINES = [
    "Keys (evdev):",
    "  Arrows     : move (hold for repeat)",
    "  Shift+Arrows / Ctrl+Arrows : faster / far jump",
    "  = / -      : adjust current pixel (mono or selected channel)",
    "  m          : toggle mono vs color mode",
    "  [ / ]      : select channel in color mode (R,G,B)",
    "  c          : clear all (black)",
    "  f          : fill all with current pixel color",
    "  , / .      : global brightness down / up",
    "  SPACE      : SHOW (latch)",
    "  q          : quit (clears + SHOWs)",
]

def draw_ui(screen, *, serial_port_name, led_count, ui_refresh_fps, selected_led_index,
            is_mono_mode, active_channel_index, pixel_array, global_brightness, keyboard_device_path):
    screen.clear()
    screen.addstr(0, 0, "LED Pixel UI (evdev input; single-pixel packets)")
    mode_label = "MONO" if is_mono_mode else f"COLOR[{('RGB'[active_channel_index])}]"
    header_text = (
        f"Port: {serial_port_name} | LEDs: {led_count} | FPS: {ui_refresh_fps} | "
        f"Brightness: {global_brightness} | Mode: {mode_label} | KBD: {os.path.basename(keyboard_device_path)}"
    )
    screen.addstr(1, 0, header_text[:max(1, curses.COLS - 1)])
    screen.addstr(2, 0, f"Index: {selected_led_index:>4} | Use arrows, Shift/Ctrl for speed, ',' '.' for brightness")

    red_value, green_value, blue_value = pixel_array.get_rgb8(selected_led_index)
    screen.addstr(4, 0, f"Pixel[{selected_led_index}] RGB=({red_value:3},{green_value:3},{blue_value:3})")

    ruler_width = min(led_count, curses.COLS - 2)
    if ruler_width > 0:
        screen.addstr(6, 0, "Index ruler:")
        ruler_line = ["·"] * ruler_width
        marker_position = int((selected_led_index / max(1, led_count - 1)) * (ruler_width - 1))
        ruler_line[marker_position] = "|"
        screen.addstr(7, 0, "".join(ruler_line))

    help_row_index = 9
    for help_line in HELP_LINES:
        if help_row_index >= curses.LINES - 1:
            break
        screen.addstr(help_row_index, 0, help_line)
        help_row_index += 1

    screen.refresh()

# ---------- Main loop ----------
def run_ui(screen, serial_port, serial_port_name, led_count, ui_refresh_fps, adjustment_step, keyboard_device_path):
    curses.curs_set(0)
    screen.nodelay(True)
    screen.keypad(True)  # still useful for resize handling

    # evdev keyboard
    key_state = KeyState(keyboard_device_path)

    pixel_array = PixelArray(led_count)
    selected_led_index = 0
    # default pixel color (editable)
    selected_red, selected_green, selected_blue = 64, 64, 64
    is_mono_mode = IS_MONO_DEFAULT
    active_channel_index = 0  # 0=R,1=G,2=B
    global_brightness = 255

    # Initialize device (clear all, set brightness, show)
    pixel_array.clear()
    for led_index in range(led_count):
        send_set_pixel(serial_port, led_index, 0, 0, 0)
    send_brightness(serial_port, global_brightness)
    send_show(serial_port)

    draw_ui(
        screen,
        serial_port_name=serial_port_name,
        led_count=led_count,
        ui_refresh_fps=ui_refresh_fps,
        selected_led_index=selected_led_index,
        is_mono_mode=is_mono_mode,
        active_channel_index=active_channel_index,
        pixel_array=pixel_array,
        global_brightness=global_brightness,
        keyboard_device_path=keyboard_device_path,
    )

    # Timing
    redraw_interval_seconds = 1.0 / max(1, ui_refresh_fps)
    next_redraw_time = time.time()
    last_redraw_time = next_redraw_time
    movement_repeat_hz = 60.0
    movement_repeat_interval = 1.0 / movement_repeat_hz
    next_movement_time = time.time()

    def move_selection(delta_leds: int):
        nonlocal selected_led_index
        selected_led_index = (selected_led_index + delta_leds) % led_count
        pixel_array.set_selected_pixel(selected_led_index)


    def set_and_send_pixel(led_index: int, red: int, green: int, blue: int):
        pixel_array.set_rgb8(led_index, red, green, blue)
        r8, g8, b8 = pixel_array.get_rgb8(led_index)
        send_set_pixel(serial_port, led_index, r8, g8, b8)
        send_show(serial_port)

    # Convenience for edge-triggered checks
    def key_down_edge(key_name: str) -> bool:
        return key_state.down_edge(key_name)

    # evdev keycode names
    KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN = 'KEY_LEFT', 'KEY_RIGHT', 'KEY_UP', 'KEY_DOWN'
    KEY_LEFTSHIFT, KEY_RIGHTSHIFT = 'KEY_LEFTSHIFT', 'KEY_RIGHTSHIFT'
    KEY_LEFTCTRL, KEY_RIGHTCTRL   = 'KEY_LEFTCTRL', 'KEY_RIGHTCTRL'
    KEY_M, KEY_LEFTBRACE, KEY_RIGHTBRACE = 'KEY_M', 'KEY_LEFTBRACE', 'KEY_RIGHTBRACE'
    KEY_C, KEY_F, KEY_SPACE, KEY_Q = 'KEY_C', 'KEY_F', 'KEY_SPACE', 'KEY_Q'
    KEY_COMMA, KEY_DOT = 'KEY_COMMA', 'KEY_DOT'
    KEY_EQUAL, KEY_MINUS = 'KEY_EQUAL', 'KEY_MINUS'
    KEY_KPPLUS, KEY_KPMINUS = 'KEY_KPPLUS', 'KEY_KPMINUS'


    last_selected_pixel = 0

    while True:
        # Poll keyboard
        key_state.poll()

        # Quit
        if key_state.is_pressed(KEY_LEFTCTRL) and key_state.is_pressed(KEY_C):
            pixel_array.clear()
            for led_index in range(led_count):
                send_set_pixel(serial_port, led_index, 0, 0, 0)
            send_show(serial_port)
            return

        if key_down_edge(KEY_Q):
            pixel_array.clear()
            for led_index in range(led_count):
                send_set_pixel(serial_port, led_index, 0, 0, 0)
            send_show(serial_port)
            return

        # Mode toggles
        if key_down_edge(KEY_M):
            is_mono_mode = not is_mono_mode
        if key_down_edge(KEY_LEFTBRACE):
            active_channel_index = (active_channel_index - 1) % 3
        if key_down_edge(KEY_RIGHTBRACE):
            active_channel_index = (active_channel_index + 1) % 3

        # Fill / Clear
        if key_down_edge(KEY_F):
            for led_index in range(led_count):
                set_and_send_pixel(led_index, selected_red, selected_green, selected_blue)
            send_show(serial_port)

        if key_down_edge(KEY_C):
            pixel_array.clear()
            for led_index in range(led_count):
                send_set_pixel(serial_port, led_index, 0, 0, 0)
            send_show(serial_port)

        # Brightness adjustments (hold-friendly)
        if KEY_COMMA in key_state.pressed_keys:  # dim
            global_brightness = max(0, global_brightness - adjustment_step)
            send_brightness(serial_port, global_brightness)
            send_show(serial_port)
        if KEY_DOT in key_state.pressed_keys:    # brighten
            global_brightness = min(255, global_brightness + adjustment_step)
            send_brightness(serial_port, global_brightness)
            send_show(serial_port)

        # Space to SHOW
        if key_down_edge(KEY_SPACE):
            send_show(serial_port)

        ##############################
        # Pixel value adjust (hold-friendly)
        current_time = time.time()

        is_increase_pressed = (KEY_EQUAL in key_state.pressed_keys) or (KEY_KPPLUS in key_state.pressed_keys)
        is_decrease_pressed = (KEY_MINUS in key_state.pressed_keys) or (KEY_KPMINUS in key_state.pressed_keys)
        if is_increase_pressed or is_decrease_pressed:
            delta_value = adjustment_step if is_increase_pressed else -adjustment_step
            if is_mono_mode:
                new_value = max(0, min(255, max(selected_red, selected_green, selected_blue) + delta_value))
                fv = selected_green = selected_blue = new_value
            else:
                if active_channel_index == 0:
                    selected_red = max(0, min(255, selected_red + delta_value))
                elif active_channel_index == 1:
                    selected_green = max(0, min(255, selected_green + delta_value))
                else:
                    selected_blue = max(0, min(255, selected_blue + delta_value))
            pixel_array.set_selected_color(selected_red, selected_green, selected_blue)


        # Continuous movement while held (with modifiers)
        if current_time >= next_movement_time:
            is_shift_down = key_state.is_pressed(KEY_LEFTSHIFT) or key_state.is_pressed(KEY_RIGHTSHIFT)
            is_ctrl_down  = key_state.is_pressed(KEY_LEFTCTRL)  or key_state.is_pressed(KEY_RIGHTCTRL)

            movement_step_multiplier = 1
            if is_shift_down:
                movement_step_multiplier = 3
            if is_ctrl_down:
                movement_step_multiplier = 12

            has_moved = False
            if KEY_LEFT in key_state.pressed_keys:
                move_selection(-movement_step_multiplier)
                has_moved = True
            if KEY_RIGHT in key_state.pressed_keys:
                move_selection(+movement_step_multiplier)
                has_moved = True
            if KEY_UP in key_state.pressed_keys:
                move_selection(+5 * movement_step_multiplier)   # page-ish up
                has_moved = True
            if KEY_DOWN in key_state.pressed_keys:
                move_selection(-9 * movement_step_multiplier)   # page-ish down
                has_moved = True

            if has_moved:
                movement_interval = movement_repeat_interval / (2 if is_shift_down else 1)
                movement_interval = movement_interval / (2 if is_ctrl_down else 1)
                next_movement_time = current_time + max(0.002, movement_interval)
            else:
                next_movement_time = current_time + 0.005  # idle check interval


        # Redraw UI
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
                led_count=led_count,
                ui_refresh_fps=ui_refresh_fps,
                selected_led_index=selected_led_index,
                is_mono_mode=is_mono_mode,
                active_channel_index=active_channel_index,
                pixel_array=pixel_array,
                global_brightness=global_brightness,
                keyboard_device_path=keyboard_device_path,
            )
            next_redraw_time = current_time + redraw_interval_seconds

        time.sleep(0.001)

def main():
    argument_parser = argparse.ArgumentParser(
        description="Keyboard UI (evdev) for single-pixel NeoPixel protocol (SET_PIXEL + SHOW + BRIGHTNESS)."
    )
    argument_parser.add_argument("--port", help="Serial port (e.g., /dev/ttyACM0). Defaults to auto-detect.")
    argument_parser.add_argument("--baud", type=int, default=DEFAULT_BAUD_RATE, help="Baud rate (default 1000000).")
    argument_parser.add_argument("--num-leds", type=int, default=288, help="Number of LEDs.")
    argument_parser.add_argument("--fps", type=int, default=50, help="UI redraw rate in frames per second.")
    argument_parser.add_argument("--step", type=int, default=8, help="Value step for +/- edits and brightness.")
    argument_parser.add_argument("--kbd", help="Keyboard event device path (e.g., /dev/input/by-id/usb-XXX-event-kbd). Autodetect if omitted.")
    args = argument_parser.parse_args()

    serial_port_name = args.port or auto_detect_port()
    if not serial_port_name:
        _, detected_ports_all = list_candidate_ports()
        print("No Arduino serial port auto-detected. Try --port /dev/ttyACM0", file=sys.stderr)
        if detected_ports_all:
            print("Detected ports:", ", ".join(detected_ports_all), file=sys.stderr)
        sys.exit(1)

    keyboard_device_path = args.kbd or auto_detect_keyboard_device_path()
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
