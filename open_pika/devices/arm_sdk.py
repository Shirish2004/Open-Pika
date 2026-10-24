"""Arm via the piper_sdk CAN interface (SDK backend).

Units: CAN integers are 0.001 mm and 0.001 deg — translated into metres and
radians here so nothing above this file ever sees vendor units.
"""
from __future__ import annotations

import math

from open_pika.devices.base import ArmState, BaseDevice, DeviceInfo
from open_pika.utils.log import get_logger

logger = get_logger("arm_sdk")


class ArmSdk(BaseDevice):
    kind = "arm"

    def __init__(self, can_port: str, move_spd_rate: int = 30, name: str = "piper"):
        super().__init__(name)
        self.info = DeviceInfo(kind=self.kind, id=name, detail=f"CAN {can_port}")
        self.can_port = can_port
        self.move_spd_rate = move_spd_rate
        self._piper = None

    def connect(self) -> bool:
        try:
            from piper_sdk import C_PiperInterface_V2
        except ImportError as exc:
            logger.error("piper_sdk not installed: %s", exc)
            return False
        try:
            self._piper = C_PiperInterface_V2(self.can_port)
            self._piper.ConnectPort()
        except Exception as exc:
            logger.error("Cannot open CAN port '%s': %s", self.can_port, exc)
            return False
        return True

    def enable(self) -> bool:
        self._piper.EnableArm(7)
        self._piper.ModeCtrl(ctrl_mode=0x01, move_mode=0x02,
                             move_spd_rate_ctrl=self.move_spd_rate)
        return True

    def disable(self) -> None:
        self._piper.DisableArm(7)

    def get_state(self) -> ArmState:
        joint = self._piper.GetArmJointMsgs()
        jv = joint.joint_state
        lp = self._piper.GetArmEndPoseMsgs().end_pose
        return ArmState(
            joint_pos=[math.radians(v * 0.001) for v in
                       (jv.J1, jv.J2, jv.J3, jv.J4, jv.J5, jv.J6)],
            joint_vel=None,
            ee_pos=[lp.X_axis * 0.001, lp.Y_axis * 0.001, lp.Z_axis * 0.001],
            ee_rpy=[math.radians(lp.RX_axis * 0.001),
                    math.radians(lp.RY_axis * 0.001),
                    math.radians(lp.RZ_axis * 0.001)],
            stamp=__import__("time").time(),
        )

    def send_ee_pose(self, xyz_m, rpy_rad) -> None:
        """EndPoseCtrl wants 0.001 mm and 0.001 deg integers."""
        self._piper.EndPoseCtrl(
            int(round(xyz_m[0] * 1000)),
            int(round(xyz_m[1] * 1000)),
            int(round(xyz_m[2] * 1000)),
            int(round(math.degrees(rpy_rad[0]) * 1000)),
            int(round(math.degrees(rpy_rad[1]) * 1000)),
            int(round(math.degrees(rpy_rad[2]) * 1000)),
        )

    def describe(self) -> str:
        return f"Piper arm over CAN '{self.can_port}'"
