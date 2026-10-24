"""Feature schema + frame builders for the dataset.

One place defines what a recorded frame contains, so the schema taught to
lerobot and the values filled per tick can't drift apart.

Feature plan (LeRobot-style):

* ``action``              float32 [7] : arm joint targets (rad, 6) + gripper (0..1, 1)
* ``observation.state``   float32 [13]: measured joints (6) + ee xyz (3) + ee rpy (3)
* ``observation.gripper`` float32 [1] : gripper normalised opening
* ``observation.sense``   float32 [7] : sense encoder (1) + imu acc (3) + gyr (3)
* ``observation.images.<cam>``        : video streams, one per selected camera
"""
from __future__ import annotations

import numpy as np

from open_pika.devices.base import ArmState, GripperState, SenseState

JOINTS = 6


def build_features(camera_names: list[str]) -> dict:
    """LeRobot features dict; camera entries keyed by chosen camera names."""
    features = {
        "action": {
            "dtype": "float32",
            "shape": [JOINTS + 1],
            "info": "6 piper joint targets (rad) + gripper 0..1",
        },
        "observation.state": {
            "dtype": "float32",
            "shape": [JOINTS],
            "info": "measured piper joint positions (rad)",
        },
        "observation.end_pose": {
            "dtype": "float32",
            "shape": [6],
            "info": "measured ee xyz (m) + rpy (rad)",
        },
        "observation.gripper": {
            "dtype": "float32",
            "shape": [1],
            "info": "gripper normalised opening 0..1",
        },
        "observation.sense": {
            "dtype": "float32",
            "shape": [7],
            "info": "sense encoder rad (1) + imu acc (3) + imu gyr (3)",
        },
    }
    for cam in camera_names:
        features[f"observation.images.{cam}"] = {"dtype": "video"}
    return features


def _floats(x, default=0.0):
    """Best-effort float conversion of a None-y vector."""
    if x is None:
        return None
    return [float(v) for v in x]


def build_frame(arm: ArmState, gripper: GripperState, sense: SenseState,
                action_joints, action_gripper) -> dict:
    """Compose the numeric part of one dataset frame.

    ``action`` uses the *next* tick's measurement (see DatasetPump for the
    double-buffering that makes this work) — standard 'action is where the
    arm ends up' convention, valid for EE-teleop rigs without joint IK.
    """
    joints = np.asarray(arm.joint_pos or [0.0] * JOINTS, dtype=np.float32)
    pose = np.asarray((arm.ee_pos or [0.0] * 3) + (arm.ee_rpy or [0.0] * 3),
                      dtype=np.float32)
    gripper_pos = np.asarray([gripper.position if gripper.position is not None else 0.0],
                             dtype=np.float32)

    enc = sense.encoder_rad if sense.encoder_rad is not None else 0.0
    acc = sense.acc or [0.0] * 3
    gyr = sense.gyr or [0.0] * 3
    sense_vec = np.asarray([enc] + list(acc) + list(gyr), dtype=np.float32)

    return {
        "action": np.asarray(
            list(action_joints or [0.0] * JOINTS) + [action_gripper],
            dtype=np.float32),
        "observation.state": joints,
        "observation.end_pose": pose,
        "observation.gripper": gripper_pos,
        "observation.sense": sense_vec,
    }
