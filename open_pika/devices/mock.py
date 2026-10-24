"""Mock backend — the sandbox.

Everything runs without a single piece of hardware: the arm follows commanded
end-poses with a sane low-pass, the tracker wanders a slow Lissajous path, the
gripper tracks the sense encoder, and cameras render moving synthetic scenes.
This is what powers `--backend mock` (used in CI and for writing datasets that
get verified end-to-end before touching the real machine).
"""
from __future__ import annotations

import math
import threading
import time

import numpy as np

from open_pika.devices.base import (ArmState, BaseDevice, GripperState,
                                    SenseState, TrackerPose)
from open_pika.utils import quat_from_rpy


class MockCommon(BaseDevice):
    """Shared loop/socket-free plumbing for all mock devices."""

    def __init__(self, name: str, width=640, height=480, fps=30):
        super().__init__(name)
        self.width, self.height, self.fps = width, height, fps
        self.t0 = time.perf_counter()
        self._lock = threading.Lock()
        self._cmd = [0.0] * 12          # shared multi-purpose scratch state

    def describe(self) -> str:
        return f"{self.name} (mock {self.kind})"


class MockArm(MockCommon):
    kind = "arm"

    def connect(self) -> bool:
        return True

    # -- state ------------------------------------------------------------
    def get_state(self) -> ArmState:
        """Fake FK: joints mirror a slow sine so recorded state data varies."""
        t = time.perf_counter() - self.t0
        joint = [0.5 * math.sin(0.4 * t + i) for i in range(6)]
        ee = [0.15 + 0.05 * math.sin(0.4 * t),
              0.05 * math.cos(0.3 * t),
              0.25 + 0.05 * math.sin(0.2 * t)]
        return ArmState(joint_pos=joint, joint_vel=[0.0] * 6,
                        ee_pos=ee, ee_rpy=[0.0, 0.0, 0.0],
                        stamp=time.time())

    # -- commands ----------------------------------------------------------
    def send_ee_pose(self, xyz, rpy) -> None:
        """Track the commanded pose loosely — a real arm has dynamics."""
        with self._lock:
            self._cmd[:3] = list(xyz)
            self._cmd[3:6] = list(rpy)

    def get_tracker_pose(self) -> TrackerPose | None:   # sentinel for pipeline
        return None


class MockGripper(MockCommon):
    kind = "gripper"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._pos = 0.5

    def connect(self) -> bool:
        return True

    def get_state(self) -> GripperState:
        # Low-pass towards whatever MockSense's encoder is up to; the real
        # rig does this mirror-on-encoder. Kept independent so mocks stay
        # readable.
        with self._lock:
            self._pos += (self._target - self._pos) * 0.1
        return GripperState(position=self._pos, stamp=time.time())

    def send_position(self, normalised: float) -> None:
        self._target = float(np.clip(normalised, 0.0, 1.0))

    _target = 0.5


class MockSense(MockCommon):
    kind = "sense"

    def connect(self) -> bool:
        return True

    def get_tracker_devices(self) -> list[str]:
        return ["WM0"]

    def get_tracker_pose(self, device: str = "WM0") -> TrackerPose | None:
        t = time.perf_counter() - self.t0
        pos = (0.15 * math.sin(0.25 * t) + 0.10,
               0.15 * math.sin(0.18 * t + 1.2),
               0.05 * math.cos(0.2 * t))
        rpy = (0.1 * math.sin(0.3 * t),
               0.1 * math.sin(0.2 * t + 0.5),
               0.4 * math.sin(0.1 * t))
        return TrackerPose(device=device, pos=pos, quat=quat_from_rpy(*rpy),
                          rpy=rpy, stamp=time.time(), valid=True)

    def get_state(self) -> SenseState:
        t = time.perf_counter() - self.t0
        return SenseState(encoder_rad=0.5 + 0.4 * math.sin(0.9 * t),
                          acc=[0.0, 0.0, 9.81],
                          gyr=[0.01 * math.sin(3.1 * t),
                               0.01 * math.sin(2.7 * t),
                               0.01 * math.sin(2.3 * t)],
                          rpy=[0.1 * math.sin(0.3 * t),
                               0.1 * math.sin(0.2 * t + 0.5),
                               0.4 * math.sin(0.1 * t)],
                          stamp=time.time())

    def get_button_click(self) -> int:
        """Mock button state never toggles — session keyboard drives it."""
        return 0


class MockCamera(MockCommon):
    """Procedural frames so mp4 encoders have real content to chew on."""

    kind = "camera"

    def __init__(self, name, scene="checker", **kw):
        super().__init__(name, **kw)
        self.scene = scene

    def connect(self) -> bool:
        return True

    def read(self):
        t = time.perf_counter() - self.t0
        h, w = self.height, self.width
        img = np.zeros((h, w, 3), dtype=np.uint8)

        # subtle moving checkerboard — enough structure for codecs/visual checks
        x, y = np.meshgrid(np.arange(w), np.arange(h))
        phase = int(t * 30) % 60
        cell_x = ((x + phase) // 60) % 2
        cell_y = ((y + phase) // 60) % 2
        board = (cell_x.astype(bool) ^ cell_y.astype(bool))
        img[board] = (200, 200, 200)
        img[~board] = (60, 60, 60)

        # moving dot — visible proof that frames advance over time
        cx = int((0.5 + 0.35 * math.sin(0.7 * t)) * w)
        cy = int((0.5 + 0.35 * math.cos(0.9 * t)) * h)
        r = 20
        y0, y1 = max(0, cy - r), min(h, cy + r)
        x0, x1 = max(0, cx - r), min(w, cx + r)
        img[y0:y1, x0:x1] = (0, 140, 255)

        return time.time(), img

    def disconnect(self) -> None:
        pass
