"""Tracker → Piper end pose mapping.

This is the teleop math from the original workspace script
(teleop_piper_sense_gripper.py), extracted and commented so the control path
that users trust is unchanged.

Model recap:
  * The tracker reports the pika in the world frame.
  * We align every tracker pose with a fixed transform `pika_to_arm`
    (rotation mounting offset between the tracker's frame and the piper's
    end-effector frame).
  * On teleop ACTIVATE we lock the current aligned tracker pose `T_base` and
    the arm's measured end pose `T_zero`.
  * While active, the commanded arm pose is
        T_cmd = T_zero @ T_base^-1 @ T_tool_now
    i.e. the relative motion the operator makes is applied to the arm from
    its resting pose. On DEACTIVATE we snapshot the arm again, so the base
    and zero stay consistent for the next grab.
"""
from __future__ import annotations

import numpy as np

from open_pika.utils.transforms import (mat_to_xyzrpy, quat_from_rpy,
                                        rpy_from_quat, xyzrpy_to_mat)


class TrackerMapper:
    """Pure math, no threads — trivial to unit test."""

    def __init__(self, pika_to_arm: list):
        self.adj_mat = np.array(xyzrpy_to_mat(*pika_to_arm))
        self._base = np.eye(4)      # aligned tracker pose at activation
        self._zero = np.eye(4)      # arm ee pose at activation
        self.active = False

    # -- poses ---------------------------------------------------------------
    def align_pose(self, pos, rpy) -> np.ndarray:
        """Tracker pose -> tool frame (mount offset applied)."""
        return np.array(xyzrpy_to_mat(*pos, *rpy)) @ self.adj_mat

    def set_arm_home(self, ee_pos, ee_rpy) -> None:
        """Snapshot current arm ee math; call when arm stops / regrabs."""
        self._zero = np.array(xyzrpy_to_mat(*ee_pos, *ee_rpy))

    def activate(self, tracker_pos, tracker_rpy, arm_ee_pos, arm_ee_rpy) -> None:
        """Lock base + zero: arm now follows the tracker's relative motion."""
        self._base = self.align_pose(tracker_pos, tracker_rpy)
        self.set_arm_home(arm_ee_pos, arm_ee_rpy)
        self.active = True

    def deactivate(self, arm_ee_pos, arm_ee_rpy) -> None:
        self.set_arm_home(arm_ee_pos, arm_ee_rpy)
        self._base = self._zero          # keeps math continuous while idle
        self.active = False

    def compute_cmd(self, tracker_pos, tracker_rpy) -> list:
        """Commanded arm end pose (xyz + rpy) for the current tracker pose."""
        T_cur = self.align_pose(tracker_pos, tracker_rpy)
        T_cmd = self._zero @ np.linalg.inv(self._base) @ T_cur
        r = mat_to_xyzrpy(T_cmd.tolist())
        return list(r)

    # -- tracker bookkeeping ----------------------------------------------------
    def pose_valid(self, tracker_pos) -> bool:
        """pysurvive emits garbage until converged: non-zero position."""
        return abs(tracker_pos[0]) + abs(tracker_pos[1]) + abs(tracker_pos[2]) > 1e-3


# backwards-compat alias used by original workspace callsites
quaternion_to_rpy = rpy_from_quat
