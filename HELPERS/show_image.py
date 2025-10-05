from pixel_cli_ui_v4 import open_serial_port
from image_to_led import push_image_to_leds

sp = open_serial_port("/dev/ttyACM0", baud_rate=1_000_000, timeout=0.0)
push_image_to_leds("ASSETS/glyphs_16/B.png", sp, 16, 16, serpentine=True, origin="bottom_left", mode="fit", background=(0,0,0), gamma=0.75)
sp.close()
