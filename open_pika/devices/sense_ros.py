"""Sense via ROS (backend=ros).

There's no vendor ROS driver for the pika sense in this workspace, so ROS-mode
"sense" has three honest sources, all optional:

* tracker_topic  (geometry_msgs/PoseStamped) — an external tracker published
  by any node (vive humans, mocap stack, ...). This is what teleop needs.
* imu_topic      (sensor_msgs/Imu)           — sensor_tools /imu/data.
* encoder_topic  (std_msgs/Float64)          — an external encoder publisher.

If none gives a tracker, the session runs "keyboard jog" mode instead of
tracker teleop — that's a separate, explicit path, not a silent fallback.
"""
from __future__ import annotations

import time

from open_pika.devices.base import BaseDevice, DeviceInfo, SenseState, TrackerPose
from open_pika.devices.ros_ipc import LatchedValue
from open_pika.utils.log import get_logger
from open_pika.utils.transforms import rpy_from_quat

logger = get_logger("sense_ros")


class SenseRos(BaseDevice):
    kind = "sense"

    def __init__(self, bridge, tracker_topic: str = "",
                 imu_topic: str = "/imu/data"):
        super().__init__("pika_sense_ros")
        self.info = DeviceInfo(kind=self.kind, id="pika_sense_ros",
                               detail=tracker_topic or "(no tracker topic)")
        self.node = bridge.node
        self._tracker = LatchedValue()
        self._imu = LatchedValue()

        if tracker_topic:
            from geometry_msgs.msg import PoseStamped
            self.node.create_subscription(
                PoseStamped, tracker_topic, self._on_tracker, 10)
        if imu_topic:
            from sensor_msgs.msg import Imu
            self.node.create_subscription(
                Imu, imu_topic, self._on_imu, 10)

    def _on_tracker(self, msg):
        p, o = msg.pose.position, msg.pose.orientation
        rpy = rpy_from_quat(o.x, o.y, o.z, o.w)
        self._tracker.set(
            TrackerPose(device="topic", pos=(p.x, p.y, p.z),
                        quat=(o.x, o.y, o.z, o.w), rpy=rpy,
                        stamp=time.time(),
                        valid=abs(p.x) + abs(p.y) + abs(p.z) > 1e-3),
            time.time())

    def _on_imu(self, msg):
        a, g = msg.linear_acceleration, msg.angular_velocity
        self._imu.set(([a.x, a.y, a.z], [g.x, g.y, g.z]), time.time())

    def connect(self) -> bool:
        return True

    def get_tracker_devices(self) -> list[str]:
        return ["topic"] if self._tracker.get() is not None else []

    def get_tracker_pose(self, device_name=None) -> TrackerPose | None:
        return self._tracker.get()

    def get_state(self) -> SenseState:
        imu = self._imu.get()
        if imu is None:
            return SenseState(stamp=time.time())
        acc, gyr = imu
        return SenseState(acc=acc, gyr=gyr, stamp=time.time())

    def describe(self) -> str:
        return "Pika sense via ros topics (tracker/imu/encoder)"
