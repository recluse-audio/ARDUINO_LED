# pixel_protocol.py
from __future__ import annotations
from typing import Protocol

# ---------- Protocol constants ----------
START_OF_FRAME_1 = 0xA5
START_OF_FRAME_2 = 0x5A
CMD_BRIGHTNESS   = 0x13
CMD_SET_PIXEL    = 0x10
CMD_SHOW         = 0x04

def compute_crc8(data_bytes: bytes) -> int:
    checksum = 0
    for byte_value in data_bytes:
        checksum ^= byte_value
        for _ in range(8):
            checksum = ((checksum << 1) ^ 0x07) & 0xFF if (checksum & 0x80) else ((checksum << 1) & 0xFF)
    return checksum


# Provide a tiny typing Protocol so we can unit-test by injecting an object
# with a .write(bytes) method (e.g., io.BytesIO or a stub).
class _ByteWriter(Protocol):
    def write(self, data: bytes) -> int: ...

def send_set_pixel(port: _ByteWriter, pixel_index: int, r: int, g: int, b: int) -> None:
    payload = bytes([
        pixel_index & 0xFF,
        (pixel_index >> 8) & 0xFF,
        r & 0xFF, g & 0xFF, b & 0xFF
    ])
    header = bytes([
        START_OF_FRAME_1, START_OF_FRAME_2, CMD_SET_PIXEL,
        len(payload) & 0xFF, (len(payload) >> 8) & 0xFF
    ])
    crc = compute_crc8(header[2:] + payload)
    port.write(header + payload + bytes([crc]))


def send_brightness(port: _ByteWriter, value: int) -> None:
    value = max(0, min(255, int(value)))
    payload = bytes([value])
    header  = bytes([START_OF_FRAME_1, START_OF_FRAME_2, CMD_BRIGHTNESS, 0x01, 0x00])
    crc     = compute_crc8(header[2:] + payload)
    port.write(header + payload + bytes([crc]))


def send_show(port: _ByteWriter) -> None:
    header = bytes([START_OF_FRAME_1, START_OF_FRAME_2, CMD_SHOW, 0x00, 0x00])
    crc    = compute_crc8(header[2:])
    port.write(header + bytes([crc]))

