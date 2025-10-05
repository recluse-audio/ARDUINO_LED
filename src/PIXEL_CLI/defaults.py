# this defaults file is for intra-source definitions, this is not meant to be user facing.
# this file (defaults.py) is differentiated from the defaults of `CONFIG/defaults.toml` in its
# contents and scope. `CONFIG/defaults.toml` pertains to command line argument defaults that are user facing.

# src/PIXEL_CLI/defaults.py
from pathlib import Path

# Optional: read overrides from config/defaults.toml (repo-local)
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    tomllib = None

# ---- Hard defaults (single source of truth) ----
DEFAULT_BAUD_RATE = 1_000_000
DEFAULT_NUM_LEDS = 288
DEFAULT_FPS = 50
DEFAULT_STEP = 8
DEFAULT_GLOBAL_BRIGHTNESS = 64
DEFAULT_RED = 128
DEFAULT_GREEN = 128
DEFAULT_BLUE = 128

# UI behavior
FADE_TIME_SECONDS_DEFAULT = 1.0
IS_MONO_DEFAULT = False

# Optional device defaults (None means "auto-detect")
DEFAULT_PORT = None
DEFAULT_KBD = None
# These are in the defaults.toml
# port = "/dev/ttyACM0"
# kbd  = "/dev/input/by-id/usb-Raspberry_Pi_Ltd_Pi_500_Keyboard-event-kbd"

# Path to repo-local overrides
# src/PIXEL_CLI/defaults.py -> parents[2] == repo root
REPO_CFG = Path(__file__).resolve().parents[2] / "config" / "defaults.toml"


def load_repo_overrides() -> dict:
    """
    Returns dict with potential overrides from config/defaults.toml.
    Keys: 'port', 'kbd'
    Falls back to DEFAULT_PORT/DEFAULT_KBD if missing.
    """
    port = DEFAULT_PORT
    kbd = DEFAULT_KBD

    if tomllib and REPO_CFG.is_file():
        try:
            cfg = tomllib.loads(REPO_CFG.read_text(encoding="utf-8"))
            port = (cfg.get("port") or port) if isinstance(cfg.get("port"), str) else port
            kbd = (cfg.get("kbd") or kbd) if isinstance(cfg.get("kbd"), str) else kbd
        except Exception:
            # ignore malformed file; use hard defaults
            pass

    return {"port": port, "kbd": kbd}
