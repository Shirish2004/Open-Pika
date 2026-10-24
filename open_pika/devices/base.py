"""Shared unit conventions for every device adapter.

Getting units wrong is the single most common source of teleop crashes, so
everything above the device layer deals in SI only:

* lengths    -> metres
* angles     -> radians
* quaternions-> (qx, qy, qz, qw)
* images     -> HxWx3 uint8 BGR (OpenCV convention)

Each adapter is responsible for translating from its vendor's units (CAN
0.001 mm integers, motor serial degrees, ROS msg fields, ...) into these.
Anything that cannot be provided by a backend returns ``None`` rather than a
fake zero — zeros are data, ``None`` is "no measurement".
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TrackerPose:
    """A single tracker sample, in metres and radians."""

    device: str
    pos: tuple[float, float, float]                 # xyz, metres
    quat: tuple[float, float, float, float]         # xyzw
    rpy: tuple[float, float, float]                 # radians
    stamp: float                                    # time.time() of arrival
    valid: bool = True


@dataclass
class ArmState:
    """Joint + end-effector state of the arm. Both may not be available."""

    joint_pos: Optional[list] = None                # 6 floats, radians
    joint_vel: Optional[list] = None                # 6 floats, rad/s
    ee_pos: Optional[list] = None                   # xyz metres
    ee_rpy: Optional[list] = None                   # radians
    stamp: float = 0.0


@dataclass
class GripperState:
    position: float = 0.0                           # normalised 0..1 (1 = open)
    angle_rad: Optional[float] = None               # raw motor angle
    distance_mm: Optional[float] = None             # jaw opening
    stamp: float = 0.0


@dataclass
class SenseState:
    encoder_rad: Optional[float] = None             # sense twist encoder
    acc: Optional[list] = None                      # m/s^2
    gyr: Optional[list] = None                      # rad/s
    rpy: Optional[list] = None                      # from onboard IMU fusion
    stamp: float = 0.0


@dataclass
class DeviceInfo:
    """Little descriptor the interactive session can show in menus."""

    kind: str                                       # arm / gripper / sense / camera
    id: str                                         # unique per device
    detail: str = ""                                # port, serial, topic ...
    extra: dict = field(default_factory=dict)


class BaseDevice(ABC):
    """Common lifecycle for all adapters: connect(), disconnect(), info()."""

    def __init__(self, name: str):
        self.name = name
        self.info = DeviceInfo(kind=self.kind, id=name)

    @property
    @abstractmethod
    def kind(self) -> str:
        """Which Protocol slot this fills: arm, gripper, sense, camera."""

    def connect(self) -> bool:
        """Try to bring the device up. Return False on failure."""
        return True

    def disconnect(self) -> None:
        pass

    @abstractmethod
    def describe(self) -> str:
        """One-line human description, e.g. in the camera-selection menu."""
