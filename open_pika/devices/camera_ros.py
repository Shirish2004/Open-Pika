"""Camera via ROS topics (backend=ros).

Any sensor_msgs/Image or CompressedImage topic becomes a dataset camera.
cv_bridge is used when present; a manual numpy decode runs when it isn't
(Humble still ships cv_bridge with the right numpy bindings, this is just
belt-and-braces for mixed envs).
"""
from __future__ import annotations

import io
import time

from open_pika.devices.base import BaseDevice, DeviceInfo
from open_pika.devices.ros_ipc import LatchedValue
from open_pika.utils.log import get_logger

logger = get_logger("camera_ros")


class CameraRos(BaseDevice):
    kind = "camera"

    def __init__(self, bridge, topic: str):
        super().__init__(topic)
        self.info = DeviceInfo(kind=self.kind, id=topic, detail=topic)
        self.node = bridge.node
        self.topic = topic
        self._buf = LatchedValue()

        self._bridge = None
        try:
            from cv_bridge import CvBridge
            self._bridge = CvBridge()
        except ImportError:
            logger.debug("cv_bridge missing — falling back to numpy decode.")

        from sensor_msgs.msg import CompressedImage
        from sensor_msgs.msg import Image as ImageMsg

        # Topic convention decides the type: ".../compressed" -> compressed,
        # anything else -> raw Image. "auto" subscribes to both spellings.
        if topic == "auto":
            base, want_raw = topic, False
        elif topic.endswith("/compressed"):
            base, want_raw = topic[:-len("/compressed")], False
        else:
            base, want_raw = topic, True
        self._subs = []
        if want_raw or topic == "auto":
            self._subs.append(self.node.create_subscription(
                ImageMsg, base, self._on_image, 10))
        if not want_raw:
            self._subs.append(self.node.create_subscription(
                CompressedImage, base + "/compressed", self._on_compressed, 10))

    def _on_image(self, msg):
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9 or time.time()
        try:
            if self._bridge is not None:
                img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            else:
                img = _decode_raw(msg)
        except Exception as exc:
            logger.debug("decode failed for %s: %s", self.topic, exc)
            return
        self._buf.set(img, stamp)

    def _on_compressed(self, msg):
        try:
            import cv2
            arr = cv2.imdecode(io.BytesIO(bytes(msg.data)), cv2.IMREAD_COLOR)
            if arr is not None:
                self._buf.set(arr, time.time())
        except Exception as exc:
            logger.debug("compressed decode failed for %s: %s", self.topic, exc)

    def connect(self) -> bool:
        return True

    def read(self):
        frame = self._buf.get()
        stamp = self._buf.stamp or time.time()
        return stamp, frame

    def describe(self) -> str:
        return f"{self.topic} (ros image topic)"


def _decode_raw(msg):
    """Minimal CV-free Image -> numpy copy for the common 8-bit RGB/BGR cases."""
    import numpy as np
    enc = msg.encoding.lower()
    if enc in ("rgb8", "bgr8"):
        arr = np.frombuffer(bytes(msg.data), dtype=np.uint8)
        arr = arr.reshape(msg.height, msg.width, 3)
        return arr[:, :, ::-1] if enc == "rgb8" else arr
    raise ValueError(f"unsupported encoding '{msg.encoding}' for manual decode")
