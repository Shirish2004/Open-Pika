"""Gripper via ROS (backend=ros).

Reads the gripper joint from /puppet/joint_<arm_name> (index 6, published by
piper_ros) and, when sensor_tools is running, the richer /gripper/data +
/imu/data streams. Commands go out as a normalised 0..1 on our own topic —
the piper_ros gripper takes its angle from joint index 6 of
joint_ctrl_single, which ArmRos already packs when it publishes, so
GripperRos only owns the normalised value bookkeeping.
"""
from __future__ import annotations

import time

from open_pika.devices.base import BaseDevice, DeviceInfo, GripperState
from open_pika.devices.ros_ipc import LatchedValue
from open_pika.utils.log import get_logger

logger = get_logger("gripper_ros")


class GripperRos(BaseDevice):
    kind = "gripper"

    def __init__(self, bridge, arm_name: str = "left", max_mm: float = 80.0):
        super().__init__("pika_gripper")
        self.info = DeviceInfo(kind=self.kind, id="pika_gripper",
                               detail=f"ros joint index 6 of /puppet/joint_{arm_name}")
        self.node = bridge.node
        self.max_mm = max_mm

        from data_msgs.msg import Gripper as GripperMsg   # data_tools msgs
        from sensor_msgs.msg import JointState

        self._arm_gripper = LatchedValue()   # rad angle from joint topic
        self._gripper_data = LatchedValue()  # data_msgs/Gripper, when avail.
        self._target = 0.0

        self.node.create_subscription(
            JointState, f"/puppet/joint_{arm_name}",
            lambda m: self._arm_gripper.set(
                list(m.position)[6] if len(m.position) > 6 else 0.0,
                time.time()), 10)
        try:
            self.node.create_subscription(
                GripperMsg, "/gripper/data",
                lambda m: self._gripper_data.set(m, time.time()), 10)
        except Exception:
            logger.info("data_msgs not on this machine — /gripper/data unused.")

    def connect(self) -> bool:
        return True

    def get_state(self) -> GripperState:
        rad = self._arm_gripper.get()
        gd = self._gripper_data.get()
        if gd is not None:                      # sensor_tools path: real mm
            mm = gd.distance
            return GripperState(position=self._norm(mm), distance_mm=mm,
                                stamp=time.time())
        if rad is None:
            return GripperState(stamp=time.time())
        return GripperState(position=self._norm_from_rad(rad),
                            angle_rad=rad, stamp=time.time())

    def send_position(self, normalised_0_1: float) -> None:
        self._target = max(0.0, min(1.0, normalised_0_1))

    def target_norm(self) -> float:
        """Let the arm adapter pack this into joint_ctrl_single index 6."""
        return self._target

    def disable(self) -> None:
        pass

    def _norm(self, mm: float) -> float:
        return max(0.0, min(1.0, mm / max(self.max_mm, 1e-6)))

    def _norm_from_rad(self, rad: float) -> float:
        # piper_ros gripper stroke over rad is an empirical ~1.0 rad wedge;
        # overridable in config once per machine if the mapping is off.
        return max(0.0, min(1.0, rad / 1.0))

    def describe(self) -> str:
        return "Pika gripper via ros topics"
