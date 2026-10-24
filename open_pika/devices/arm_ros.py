"""Arm via piper_ros topics (ROS backend).

Expects an already-running piper_ros bring-up (ours: launch/ros_backend.launch.py):

    /puppet/joint_<name>     JointState  — measured joints (index 6 = gripper)
    /puppet/end_pose_<name>  PoseStamped — measured end pose
    joint_ctrl_single        JointState  — joint commands, radians
    enable_flag              Bool        — arm enable/disable
"""
from __future__ import annotations

import time

from open_pika.devices.base import ArmState, BaseDevice, DeviceInfo
from open_pika.devices.ros_ipc import LatchedValue
from open_pika.utils.log import get_logger
from open_pika.utils.transforms import rpy_from_quat

logger = get_logger("arm_ros")


class ArmRos(BaseDevice):
    kind = "arm"

    def __init__(self, bridge, arm_name: str = "left"):
        super().__init__(f"piper_{arm_name}")
        self.info = DeviceInfo(kind=self.kind, id=f"piper_{arm_name}",
                               detail=f"ros /puppet/joint_{arm_name}")
        self.bridge = bridge
        self.node = bridge.node
        self.arm_name = arm_name

        from geometry_msgs.msg import PoseStamped
        from sensor_msgs.msg import JointState
        from std_msgs.msg import Bool

        self._meas_joint = LatchedValue()   # ([6 joints rad], gripper rad)
        self._meas_pose = LatchedValue()    # (xyz m, rpy rad)
        self._arm_joints = [0.0] * 6
        self._gripper_angle = 0.0

        self.node.create_subscription(
            JointState, f"/puppet/joint_{arm_name}", self._on_joint, 10)
        self.node.create_subscription(
            PoseStamped, f"/puppet/end_pose_{arm_name}", self._on_pose, 10)
        self._ctrl_pub = self.node.create_publisher(JointState, "joint_ctrl_single", 10)
        self._flag_pub = self.node.create_publisher(Bool, "enable_flag", 10)

    # -- callbacks -----------------------------------------------------------
    def _on_joint(self, msg):
        pos = list(msg.position)
        self._meas_joint.set((pos[:6], pos[6] if len(pos) > 6 else 0.0),
                             time.time())

    def _on_pose(self, msg):
        p, o = msg.pose.position, msg.pose.orientation
        self._meas_pose.set(
            ([p.x, p.y, p.z], rpy_from_quat(o.x, o.y, o.z, o.w)),
            time.time())

    # -- lifecycle -----------------------------------------------------------
    def connect(self) -> bool:
        # piper_ros bring-up is external; if nothing publishes there's no
        # measured joint topic and the session flags it, no magic here.
        return True

    def enable(self) -> bool:
        from std_msgs.msg import Bool
        self._flag_pub.publish(Bool(data=True))
        return True

    def disable(self) -> None:
        from std_msgs.msg import Bool
        self._flag_pub.publish(Bool(data=False))

    # -- state -----------------------------------------------------------------
    def get_state(self) -> ArmState:
        j = self._meas_joint.get()
        p = self._meas_pose.get()
        if j is None:
            return ArmState(stamp=time.time())
        joints, gripper = j
        self._arm_joints, self._gripper_angle = joints, gripper
        if p is None:
            return ArmState(joint_pos=joints, stamp=time.time())
        pos, rpy = p
        return ArmState(joint_pos=joints, ee_pos=pos, ee_rpy=rpy,
                        stamp=time.time())

    # -- commands ---------------------------------------------------------------
    def send_ee_pose(self, xyz, rpy) -> None:
        # piper_ros only exposes joint-space control; EE poses would need IK.
        # Keep the current joints, just re-publish them (no-op) — callers that
        # really want EE motion should use the sdk backend.
        logger.warning("send_ee_pose is a no-op on ros backend; use send_joints.")

    def send_joints(self, joints_rad, gripper_norm=0.0) -> None:
        self._arm_joints = list(joints_rad)
        self._gripper_angle = gripper_norm
        self._ctrl_pub.publish(self._joint_msg(list(joints_rad) + [gripper_norm]))

    def _joint_msg(self, positions):
        from sensor_msgs.msg import JointState
        msg = JointState()
        msg.header.stamp = self.node.get_clock().now().to_msg()
        msg.name = [f"joint{i}" for i in range(len(positions))]
        msg.position = list(positions)
        return msg

    def describe(self) -> str:
        return f"Piper '{self.arm_name}' via ros topics"
