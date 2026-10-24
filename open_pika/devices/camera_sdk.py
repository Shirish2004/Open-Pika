"""Cameras via the pika SDK (fisheye on Sense/Gripper, RealSense D405).

The SDK exposes cameras through the Sense/Gripper objects themselves, so this
adapter takes a *host* (the sense or gripper adapter) rather than talking to
hardware directly. The host decides which camera to hand out; we standardise
on `read() -> (timestamp, BGR ndarray)`.
"""
from __future__ import annotations

import time

from open_pika.devices.base import BaseDevice, DeviceInfo
from open_pika.utils.log import get_logger

logger = get_logger("camera_sdk")


class SdkCamera(BaseDevice):
    kind = "camera"

    def __init__(self, name: str, host, picker, width, height, fps):
        """`picker(host)` returns the vendor camera object once warm."""
        super().__init__(name)
        self.info = DeviceInfo(kind=self.kind, id=name, detail=str(host))
        self._host = host
        self._picker = picker
        self.width, self.height, self.fps = width, height, fps
        self._cam = None

    def connect(self) -> bool:
        try:
            self._cam = self._picker(self._host)
        except Exception as exc:
            logger.error("camera '%s' init failed: %s", self.name, exc)
            return False
        return self._cam is not None

    def read(self):
        """Latest frame or (time.time(), None) when nothing new yet.

        The vendor cameras run their own read threads internally; we only
        poll, we never spin a second thread per camera.
        """
        if self._cam is None:
            return time.time(), None
        frame = self._get_latest()
        return time.time(), frame

    def _get_latest(self):
        # Two vendor interfaces exist: fisheye get_frame() -> (ok, np-img),
        # real get_color_frame() / get_depth_frame() -> (ok, ndarray).
        getter = getattr(self._cam, "get_color_frame", None)
        if getter is not None:
            ok, frame = getter()
            return frame if ok else None
        return getattr(self._cam, "get_frame", lambda: (False, None))[1]

    def disconnect(self) -> None:
        attr = getattr(self._cam, "disconnect", None)
        if attr:
            attr()

    def describe(self) -> str:
        return f"{self.name} (pika SDK camera)"
