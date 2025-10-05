# src/PIXEL_CLI/ui.py
import os
import curses

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

def draw_ui(
    screen,
    *,
    serial_port_name,
    led_count,
    ui_refresh_fps,
    selected_led_index,
    is_mono_mode,
    active_color_index,
    pixel_array,
    global_brightness,
    keyboard_device_path,
):
    screen.clear()
    screen.addstr(0, 0, "LED Pixel UI (evdev input; single-pixel packets)")
    mode_label = "MONO" if is_mono_mode else f"COLOR[{('RGB'[active_color_index])}]"
    header_text = (
        f"Port: {serial_port_name} | LEDs: {led_count} | FPS: {ui_refresh_fps} | "
        f"Brightness: {global_brightness} | Mode: {mode_label} | KBD: {os.path.basename(keyboard_device_path)}"
    )
    screen.addstr(1, 0, header_text[: max(1, curses.COLS - 1)])
    screen.addstr(
        2,
        0,
        f"Index: {selected_led_index:>4} | Use arrows, Shift/Ctrl for speed, ',' '.' for brightness",
    )

    red_value, green_value, blue_value = pixel_array.get_rgb8(selected_led_index)
    screen.addstr(
        4, 0, f"Pixel[{selected_led_index}] RGB=({red_value:3},{green_value:3},{blue_value:3})"
    )

    ruler_width = min(led_count, curses.COLS - 2)
    if ruler_width > 0:
        screen.addstr(6, 0, "Index ruler:")
        ruler_line = ["·"] * ruler_width
        marker_position = int(
            (selected_led_index / max(1, led_count - 1)) * (ruler_width - 1)
        )
        ruler_line[marker_position] = "|"
        screen.addstr(7, 0, "".join(ruler_line))

    help_row_index = 9
    for help_line in HELP_LINES:
        if help_row_index >= curses.LINES - 1:
            break
        screen.addstr(help_row_index, 0, help_line)
        help_row_index += 1

    screen.refresh()
