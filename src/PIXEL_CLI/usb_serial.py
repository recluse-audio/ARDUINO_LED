# src/PIXEL_CLI/usb_serial.py
"""
USB/serial helpers for PIXEL_CLI.
"""

from __future__ import annotations

import time
import serial
from serial.tools import list_ports
from PIXEL_CLI.defaults import DEFAULT_BAUD_RATE



def list_candidate_ports():
    """
    Return (candidate_devices, all_ports), where:
      - candidate_devices: ports that look like Arduino/USB-serial
      - all_ports: every discovered port device string
    """
    candidate_devices, all_ports = [], []
    for port_info in list_ports.comports():
        dev = (port_info.device or "").lower()
        desc = (port_info.description or "").lower()
        all_ports.append(port_info.device)
        if (
            "ttyacm" in dev
            or "ttyusb" in dev
            or "cu.usbmodem" in dev
            or "cu.usbserial" in dev
            or "arduino" in desc
            or "wch" in desc
            or "ch340" in desc
            or "usb serial" in desc
            or "cp210x" in desc
            or "ftdi" in desc
        ):
            candidate_devices.append(port_info.device)
    return candidate_devices, all_ports


def auto_detect_port():
    """
    Pick the first 'candidate' port if any, else None.
    """
    candidates, _ = list_candidate_ports()
    return candidates[0] if candidates else None


def open_serial_port(port_path: str, baud_rate: int = DEFAULT_BAUD_RATE, timeout: float = 0.0):
    """
    Open the serial port, wait briefly for MCU reset, and clear input.
    """
    ser = serial.Serial(port_path, baudrate=baud_rate, timeout=timeout)
    time.sleep(2.0)  # allow board to reset after opening the port
    ser.reset_input_buffer()
    return ser
