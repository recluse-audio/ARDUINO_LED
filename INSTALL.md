# Install

## System requirements
- Raspberry Pi OS / Linux with Python 3.11+
- Kernel input (evdev) available
- Serial access to Arduino-compatible board

## System packages (Debian/RPi OS)
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential libevdev2

## Permissions
# Serial: add user to 'dialout'
sudo usermod -aG dialout "$USER"

# Keyboard input: typically readable by 'input' group; add yourself or create a udev rule.
sudo usermod -aG input "$USER"

# (Log out and back in or reboot to apply group changes.)

## Clone + venv
git clone https://github.com/recluse-audio/ARDUINO_LED.git
cd ARDUINO_LED
python3 -m venv .venv
. .venv/bin/activate

## Install (users)
pip install -r requirements.txt

## Install (devs)
pip install -r requirements-dev.txt
pre-commit install

## Run
python -m pixel_cli --port /dev/ttyACM0 --kbd /dev/input/by-id/usb-XXX-event-kbd
# or, if you enable the console script entry point:
pixel-cli --port /dev/ttyACM0 --kbd /dev/input/by-id/usb-XXX-event-kbd
