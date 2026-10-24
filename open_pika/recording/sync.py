"""DatasetPump — the fixed-rate loop between devices and lerobot.

Design notes (worth remembering when recording looks wrong):

* The teleop control loop runs at ``control_hz`` (usually 50) independently.
* The dataset wants a steady ``fps`` (usually 30): the pump ticks exactly
  per-frame using a deadline loop, never spin/sleep mixups, never per-camera
  drift.
* Pillow-buffered images from the camera adapters — no second thread per
  camera; each adapter keeps only the *latest* frame, which is the right
  semantics for a teleop dataset (nearest-in-time camera view, not history).
* ``action`` for tick *i* is the arm measurement of tick *i+1* (double
  buffering). This is the convention that survives EE-teleop rigs with no
  IK-to-joints path, and matches what the piper LeRobot examples expect.
"""
from __future__ import annotations

import threading
import time

from open_pika.recording.frames import build_frame
from open_pika.utils.log import get_logger

logger = get_logger("pump")


class DatasetPump(threading.Thread):
    """Runs in its own thread; add_frame()/save_episode() happen live."""

    def __init__(self, devices, recorder, fps, task=""):
        super().__init__(daemon=True, name="dataset_pump")
        self.devices = devices
        self.recorder = recorder
        self.period = 1.0 / fps
        self.task = task

        self._recording = threading.Event()      # episode armed?
        self._stop = threading.Event()
        self._frames = 0                          # frames in current episode
        self._last_images = {}                    # per-camera fallback

    # -- public controls ------------------------------------------------------
    def start_episode(self, task: str) -> None:
        self.task = task
        self._frames = 0
        self._recording.set()

    def stop_episode(self) -> int:
        """Stop feeding; returns frame count of the (uncommitted) episode."""
        self._recording.clear()
        return self._frames

    def is_recording(self) -> bool:
        return self._recording.is_set()

    def frame_count(self) -> int:
        return self._frames

    def shutdown(self) -> None:
        self._stop.set()
        self.join(timeout=5)

    # -- the pump ---------------------------------------------------------------
    def run(self) -> None:
        logger.info("Pump running at %.1f Hz.", 1.0 / self.period)
        prev = None                  # (images, arm, gripper, sense) of tick i-1
        deadline = time.perf_counter()

        while not self._stop.is_set():
            deadline += self.period
            now = time.perf_counter()
            if deadline > now:
                time.sleep(deadline - now)
            else:
                # tick overflow: system can't keep up — log once, drop back
                deadline = now

            active = self._recording.is_set()
            snap = self._snapshot(active)
            if active and prev is not None:
                self._emit(prev, snap)
            prev = snap

        logger.info("Pump stopped.")

    def _snapshot(self, include_images: bool) -> dict:
        cameras = self.devices["cameras"]
        images = {}
        if include_images:
            for cam in cameras:
                stamp, img = cam.read()
                if img is not None:
                    self._last_images[cam.name] = img
                if cam.name in self._last_images:
                    images[cam.name] = self._last_images[cam.name]
                # A camera that has never produced a frame is simply absent
                # from this tick — the recorder still knows the schema.
        return {
            "images": images,
            "arm": self.devices["arm"].get_state(),
            "gripper": self.devices["gripper"].get_state(),
            "sense": self.devices["sense"].get_state(),
        }

    def _emit(self, prev, cur) -> None:
        """One lerobot frame from i-1 state + i action."""
        frame = build_frame(
            arm=prev["arm"],
            gripper=prev["gripper"],
            sense=prev["sense"],
            action_joints=(cur["arm"].joint_pos),
            action_gripper=next_gripper_action(prev, cur),
        )
        frame.update(pos_images(prev["images"]) if prev["images"] else {})
        try:
            self.recorder.add_frame(frame, self.task)
            self._frames += 1
        except Exception as exc:
            logger.error("add_frame failed: %s — dropping frame.", exc)


def next_gripper_action(prev, cur) -> float:
    """Same shifted-action rule as joints: next tick's gripper measurement."""
    nxt = cur["gripper"].position
    return float(0.0 if nxt is None else nxt)


def pos_images(images: dict) -> dict:
    """Images go under observation.images.<name> with RGB — lerobot encodes
    assuming RGB and OpenCV hands us BGR."""
    return {f"observation.images.{name}": img[:, :, ::-1]
            for name, img in images.items() if img is not None}
