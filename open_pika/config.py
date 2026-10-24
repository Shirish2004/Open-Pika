"""Config loading for open_pika.

A single YAML file holds hardware details (ports, CAN, camera serials) and
teleop constants. CLI flags and interactive answers override it, so the file
only needs to be right once per machine.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path

import yaml

# Shipped default, lives next to the package's config/ directory in the repo.
REPO_CONFIG = Path(__file__).resolve().parent.parent / "config" / "default.yaml"
USER_CONFIG = Path("~/.config/open_pika/config.yaml").expanduser()


_DEFAULTS = {
    "backend": "sdk",
    "control_hz": 50,
    # Serial + CAN endpoints. These differ per machine — that's what config is for.
    "sense": {"port": "/dev/ttyUSB0", "tracker_device": "WM0",
              "fisheye_index": 0, "realsense_serial": "",
              "stabilise_secs": 3.0},
    "gripper": {"port": "/dev/ttyUSB2",
                "fisheye_index": 2, "realsense_serial": ""},
    "arm": {"can_port": "can0", "move_spd_rate": 30,
            "always_on_teleop": True},
    # Camera pipeline shared by fisheye/RealSense/mocked cameras.
    "camera": {"width": 640, "height": 480, "fps": 30},
    # pose offset applied between the pika tracker frame and the piper end frame.
    # (copied from the original workspace teleop script, PIKA_TO_ARM)
    "mapping": {"pika_to_arm": [0.0, 0.0, 0.0, 0.0, 1.5707963267948966, 0.0],
                "deadzone_m": 0.001},
    "recording": {"fps": 30, "record_pose": True, "record_imu": True,
                  "video": {"codec": "libsvtav1", "pix_fmt": "yuv420p",
                            "g": 2, "crf": 30},
                  "images_buffered": False},
}


def load_config(path: str | os.PathLike | None = None) -> dict:
    """Read the user/project YAML on top of sane internal defaults.

    Never scatter os.environ lookups through the code — everything lands here
    so a printed config dump tells the whole truth about a session.
    """
    cfg = copy.deepcopy(_DEFAULTS)

    candidates = []
    if path:
        candidates.append(Path(path))
    if os.environ.get("OPEN_PIKA_CONFIG"):
        candidates.append(Path(os.environ["OPEN_PIKA_CONFIG"]))
    candidates.append(USER_CONFIG)
    candidates.append(REPO_CONFIG)

    for cand in candidates:
        if cand and cand.is_file():
            with open(cand) as fh:
                overrides = yaml.safe_load(fh) or {}
            _deep_update(cfg, overrides)
            break  # first hit wins; no surprise merging from lower-priority files

    _validate(cfg)
    return cfg


def _deep_update(base: dict, overrides: dict) -> None:
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v


def _validate(cfg: dict) -> None:
    if cfg["backend"] not in ("sdk", "ros", "mock"):
        raise ValueError(
            f"Unknown backend '{cfg['backend']}' — expected sdk, ros or mock.")
    if cfg["control_hz"] <= 0 or cfg["recording"]["fps"] <= 0:
        raise ValueError("control_hz and recording.fps must be positive.")

    p2a = cfg["mapping"]["pika_to_arm"]
    if len(p2a) != 6:
        raise ValueError("mapping.pika_to_arm must be [x, y, z, r, p, yaw].")


def dump_yaml(cfg: dict, path) -> None:
    """Write a config back out (used to persist wizard answers)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False)
