"""Small numeric helpers shared by teleop + recording."""
from __future__ import annotations

import math


def rpy_from_quat(qx, qy, qz, qw):
    """ZYX Euler from a unit quaternion (radians)."""
    rx = math.atan2(2 * (qw * qx + qy * qz), 1 - 2 * (qx * qx + qy * qy))
    sy = max(-1.0, min(1.0, 2 * (qw * qy - qz * qx)))
    ry = math.asin(sy)
    rz = math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))
    return rx, ry, rz


def quat_from_rpy(rx, ry, rz):
    """Inverse of rpy_from_quat (ZYX order)."""
    cr, cp, cy = (math.cos(a * 0.5) for a in (rx, ry, rz))
    sr, sp, sy = (math.sin(a * 0.5) for a in (rx, ry, rz))
    qx = sr * cp * cy - cr * sp * sy
    qy = cr * sp * cy + sr * cp * sy
    qz = cr * cp * sy - sr * sp * cy
    qw = cr * cp * cy + sr * sp * sy
    return (qx, qy, qz, qw)


def xyzrpy_to_mat(x, y, z, rx, ry, rz):
    """Homogeneous transform from XYZ + ZYX Euler."""
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    T = [
        [cy * cz, cy * sz, -sy, x],
        [sx * sy * cz - cx * sz, sx * sy * sz + cx * cz, sx * cy, y],
        [cx * sy * cz + sx * sz, cx * sy * sz - sx * cz, cx * cy, z],
        [0.0, 0.0, 0.0, 1.0],
    ]
    return T


def mat_to_xyzrpy(T):
    x, y, z = T[0][3], T[1][3], T[2][3]
    sy = max(-1.0, min(1.0, -T[2][0]))
    if abs(sy) > 1.0 - 1e-6:
        ry = math.copysign(math.pi / 2, sy)
        rx = math.atan2(-T[1][2], T[1][1])
        rz = 0.0
    else:
        ry = math.asin(sy)
        c = math.cos(ry)
        rx = math.atan2(T[2][1] / c, T[2][2] / c)
        rz = math.atan2(T[1][0] / c, T[0][0] / c)
    return x, y, z, rx, ry, rz
