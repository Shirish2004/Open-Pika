"""Gripper via pika.gripper serial link (SDK backend).

The pika SDK talks in both motor angle (rad) and jaw distance (mm). For the
dataset we expose a normalised "position" derived from jaw distance so mock /
ROS / SDK backends agree on one number: 0 = closed, 1 = fully open.
"""
from __future__ import annotations

import time

from open_pika.devices.base import BaseDevice, DeviceInfo, GripperState
from open_pika.utils.log import get_logger

logger = get_logger("gripper_sdk")


class GripperSdk(BaseDevice):
    kind = "gripper"

    NOMINAL_MAX_MM = 80.0      # typical Pika gripper stroke; override in cfg

    def __init__(self, port: str, max_mm: float = NOMINAL_MAX_MM):
        super().__init__("pika_gripper")
        self.info = DeviceInfo(kind=self.kind, id="pika_gripper", detail=port)
        self.port = port
        self.max_mm = max_mm
        self._g = None

    def connect(self) -> bool:
        try:
            from pika.gripper import Gripper
        except ImportError as exc:
            logger.error("pika SDK not installed: %s", exc)
            return False
        self._g = Gripper(self.port)
        if not self._g.connect():
            logger.error("Cannot open gripper serial port '%s'", self.port)
            return False
        if not self._g.enable():
            logger.error("Gripper motor enable failed on '%s'", self.port)
            return False
        return True

    def get_state(self) -> GripperState:
        mm = self._g.get_gripper_distance()
        return GripperState(position=self._norm_from_mm(mm),
                            angle_rad=self._g.get_motor_position(),
                            distance_mm=mm,
                            stamp=time.time())

    def send_position(self, normalised_0_1: float) -> None:
        self._g.set_gripper_distance(
            self.max_mm * max(0.0, min(1.0, normalised_0_1)))

    def mirror_sense_encoder(self, encoder_rad: float) -> None:
        """How the real rig is driven: copy the sense twist onto the motor."""
        self._g.set_motor_angle(encoder_rad)

    def disable(self) -> None:
        self._g.disable()

    def _norm_from_mm(self, mm: float) -> float:
        return max(0.0, min(1.0, mm / max(self.max_mm, 1e-6)))

    def describe(self) -> str:
        return f"Pika gripper on '{self.port}'"
