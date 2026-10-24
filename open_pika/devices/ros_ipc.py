"""Shared rclpy plumbing for the ROS backend.

All ROS device adapters hang off one node + spinner (RosBridge). Creating a
node per adapter would multiply subscription threads for no benefit.
Careful: this file must not import rclpy at module scope — users of the SDK
backend might not have a ROS environment at all.
"""
from __future__ import annotations

import threading


class RosBridge:
    """One rclpy node, spun in a daemon thread, shared by all ROS adapters."""

    def __init__(self, node_name: str = "open_pika_bridge"):
        import rclpy
        from rclpy.node import Node

        rclpy.init(args=None)
        self.node = Node(node_name)
        self._spin = threading.Thread(
            target=rclpy.spin, args=(self.node,), daemon=True)
        self._spin.start()

    def shutdown(self) -> None:
        try:
            self.node.destroy_node()
        except Exception:
            pass
        try:
            import rclpy
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass


class LatchedValue:
    """Thread-safe latest-of-a-topic box with its own stamp.

    Adapters subscribe a callback, drop the value in here, and the 50 Hz
    control loop / recorder just reads it twice — no lock gymnastics.
    """

    def __init__(self):
        import threading
        self._lock = threading.Lock()
        self._value = None
        self.stamp = 0.0

    def set(self, value, stamp: float) -> None:
        with self._lock:
            self._value = value
        self.stamp = stamp

    def get(self):
        with self._lock:
            return self._value
