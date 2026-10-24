"""Pika Sense via pika.sense (SDK backend).

Wraps the vendor Sense class and adds an IMU listener the same way the
original workspace script did (subclass overrides `_data_callback`, so the
base-class wiring keeps working through the MRO).
"""
from __future__ import annotations

import threading
import time

from open_pika.devices.base import BaseDevice, DeviceInfo, SenseState, TrackerPose
from open_pika.utils.log import get_logger
from open_pika.utils.transforms import rpy_from_quat

logger = get_logger("sense_sdk")


class SenseSdk(BaseDevice):
    kind = "sense"

    def __init__(self, port: str, tracker_device: str = "WM0"):
        super().__init__("pika_sense")
        self.info = DeviceInfo(kind=self.kind, id="pika_sense", detail=port)
        self.port = port
        self.tracker_device = tracker_device
        self._sense = None
        self._imu = {"acc": None, "gyr": None, "rpy": None}
        self._imu_lock = threading.Lock()

    def connect(self) -> bool:
        from pika.sense import Sense

        self._sense = SenseWithIMU(self.port, on_imu=self._on_imu)
        if not self._sense.connect():
            logger.error("Cannot open sense serial port '%s'", self.port)
            return False
        logger.info("Pika sense connected (%s).", self.port)
        return True

    def _on_imu(self, imu: dict) -> None:
        with self._imu_lock:
            self._imu = {"acc": imu.get("acc", [0.0, 0.0, 0.0]),
                         "gyr": imu.get("gyr", [0.0, 0.0, 0.0]),
                         "rpy": [imu.get("pitch", 0.0),
                                 imu.get("roll", 0.0),
                                 imu.get("yaw", 0.0)]}

    # -- tracker / IMU / encoder -------------------------------------------
    def get_tracker_devices(self) -> list[str]:
        try:
            return list(self._sense.get_tracker_devices())
        except Exception as exc:
            logger.debug("tracker_devices probe failed: %s", exc)
            return []

    def get_tracker_pose(self, device_name: str | None = None) -> TrackerPose | None:
        """L tracker pose wrapped into our SI TrackerPose, or None."""
        pose = self._sense.get_pose(device_name or self.tracker_device)
        if not pose:
            return None
        pos = pose.position
        quat = pose.rotation                    # (qx, qy, qz, qw)
        rpy = rpy_from_quat(*quat)
        return TrackerPose(device=device_name or self.tracker_device,
                           pos=tuple(pos), quat=tuple(quat), rpy=rpy,
                           stamp=time.time(),
                           valid=(abs(pos[0]) + abs(pos[1]) + abs(pos[2])) > 1e-3)

    def get_state(self) -> SenseState:
        enc = self._sense.get_encoder_data()
        with self._imu_lock:
            acc, gyr, rpy = (list(self._imu["acc"] or [0.0] * 3),
                             list(self._imu["gyr"] or [0.0] * 3),
                             list(self._imu["rpy"] or [0.0] * 3))
        return SenseState(encoder_rad=enc.get("rad"), acc=acc, gyr=gyr,
                          rpy=rpy, stamp=time.time())

    def get_fisheye_camera(self):
        return self._sense.get_fisheye_camera()

    def get_realsense_camera(self):
        return self._sense.get_realsense_camera()

    def set_camera_param(self, w, h, fps):
        self._sense.set_camera_param(w, h, fps)

    def set_fisheye_index(self, index: int):
        self._sense.set_fisheye_camera_index(index)

    def set_realsense_serial(self, serial: str):
        if serial:
            self._sense.set_realsense_serial_number(serial)

    def describe(self) -> str:
        return f"Pika sense on '{self.port}'"


class SenseWithIMU(Sense):
    """Same trick as the original script — piggyback IMU fields onto the
    vendor callback. Keeps us compatible with future pika SDK updates."""

    def __init__(self, port="/dev/ttyUSB0", on_imu=None):
        super().__init__(port)
        self._on_imu = on_imu

    def _data_callback(self, data):
        super()._data_callback(data)
        try:
            with self.data_lock:
                if "IMU" in data:
                    imu = data["IMU"]
                    if self._on_imu:
                        self._on_imu(imu)
        except Exception as exc:
            logger.error("imu callback error: %s", exc)
