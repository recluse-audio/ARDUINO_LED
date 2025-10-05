# PIXEL_CLI (Linux)

Minimal steps to set up the Python env, install packages, and run the app.

## 1) System prerequisites (Debian/Ubuntu/Raspberry Pi OS)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip build-essential
# (Optional but recommended) serial & input access without sudo:
sudo usermod -a -G dialout $USER     # for /dev/ttyACM*
sudo usermod -a -G input $USER       # for /dev/input/*
# Log out and back in after changing groups.
```

> If you prefer, run the tool with `sudo` instead of changing groups.

## 2) Clone and enter the repo

```bash
git clone <YOUR_REPO_URL> ARDUINO_LED
cd ARDUINO_LED
```

## 3) Create & activate a virtual environment (always named `venv`)

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
```

## 4) Install the project (editable)

```bash
pip install -e .
```

This installs all Python dependencies and creates the console command `PIXEL_CLI`.

## 5) (Optional) Repo-local defaults

Create a repo-local config to avoid long command lines:

```
mkdir -p config
nano config/defaults.toml
```

Example `config/defaults.toml`:

```toml
port = "/dev/ttyACM0"
kbd  = "/dev/input/by-id/usb-Raspberry_Pi_Ltd_Pi_500_Keyboard-event-kbd"
```

## 6) Run

With defaults file present:

```bash
PIXEL_CLI
```

Or explicitly:

```bash
PIXEL_CLI --port /dev/ttyACM0 --kbd /dev/input/by-id/usb-...-event-kbd
```

## 7) Troubleshooting (quick)

* **Permission denied on serial**: ensure you’re in the `dialout` group (or run with `sudo`).
* **Permission denied on keyboard device**: ensure you’re in the `input` group (or run with `sudo`).
* **No keyboard detected**: pass `--kbd` with the full `/dev/input/by-id/...-event-kbd` path.

## 8) Development tips

* Reinstall after dependency changes:

  ```bash
  pip install -e .
  ```
* Freeze your current env (optional):

  ```bash
  pip freeze > requirements.lock
  ```

## 9) Deactivate env

```bash
deactivate
```

---

**Project layout (key parts)**

```
ARDUINO_LED/
├─ config/
│  └─ defaults.toml           # optional repo-local defaults
├─ src/
│  └─ PIXEL_CLI/
│     ├─ __init__.py
│     ├─ pixel_cli.py         # entry point
│     ├─ usb_serial.py
│     ├─ pixel_protocol.py
│     ├─ pixel_array.py
│     ├─ pixel.py
│     └─ key_state.py
└─ pyproject.toml             # defines package & console script PIXEL_CLI
```
