"""Tracker-following controller: ties arm+gripper+sense into a control loop.

Responsibilities (each was buried in the original monolith, now explicit):
  * tracker thread — latest tool pose at control_hz
  * gripper mirrors the sense encoder (the tight human-to-robot coupling)
  * teleop trigger — sense button when the SDK provides one, always explicit
    via the session keyboard otherwise
  * activation/deactivation — the mapper's base/zero snapshot pair
"""
from __future__ import annotations

import threading
import time

from open_pika.teleop.mapper import TrackerMapper
from open_pika.utils.log import get_logger

logger = get_logger("controller")


class TeleopController:
    """Owns the tracker/control threads; drives `arm` and `gripper`."""

    def __init__(self, devices, cfg: dict, keyboard=None):
        self.devices = devices
        self.arm = devices["arm"]
        self.gripper = devices["gripper"]
        self.sense = devices["sense"]
        self.keyboard = keyboard            # session-provided hook, optional

        self.control_hz = cfg["control_hz"]
        mapping = cfg["mapping"]
        self.mapper = TrackerMapper(mapping["pika_to_arm"])
        self.always_on = cfg["arm"]["always_on_teleop"]
        self.tracker_device = cfg["sense"]["tracker_device"]
        self.stabilise_secs = cfg["sense"].get("stabilise_secs", 3.0)

        self.running = threading.Event()
        self.running.set()
        self.teleop_active = False
        self._pose_lock = threading.Lock()
        self._latest_pose = None
        self._goal_gripper = 0.5            # manual jog mode setpoint

        self._threads = [
            threading.Thread(target=self._tracker_loop, daemon=True,
                             name="tracker"),
            threading.Thread(target=self._control_loop, daemon=True,
                             name="teleop"),
            threading.Thread(target=self._diagnostic_loop, daemon=True,
                             name="diag"),
        ]

    # -- lifecycle --------------------------------------------------------------
    def start(self) -> bool:
        for t in self._threads:
            t.start()
        return True

    def stop(self) -> None:
        self.running.clear()
        for t in self._threads:
            t.join(timeout=2)

    def wait_for_tracker(self, timeout: float = 30.0) -> bool:
        """Block until the tracker device reports a sane pose."""
        deadline = time.time() + timeout
        logger.info("Waiting up to %.0fs for tracker '%s'...",
                    timeout, self.tracker_device)
        while time.time() < deadline and self.running.is_set():
            if self.sense.get_tracker_devices() and self._latest_pose is not None:
                logger.info("Tracker found; letting pysurvive stabilise "
                            "(%.1fs)...", self.stabilise_secs)
                time.sleep(self.stabilise_secs)
                return True
            time.sleep(0.5)
        logger.error("Tracker '%s' never reported a pose — is it paired?",
                     self.tracker_device)
        return False

    # -- trigger semantics --------------------------------------------------------
    def set_teleop(self, active: bool) -> None:
        """Engage/disengage tracking. Safe to call from any thread."""
        if active == self.teleop_active:
            return
        arm = self.arm.get_state()
        if arm.ee_pos is None:
            logger.warning("No arm ee pose yet — can't (de)activate teleop.")
            return
        if active:
            pose = self._latest_pose
            if pose is None or not self.mapper.pose_valid(pose.pos):
                logger.warning("No valid tracker pose — refusing activation.")
                return
            self.mapper.activate(pose.pos, pose.rpy, arm.ee_pos, arm.ee_rpy)
            self.teleop_active = True
            logger.info("Teleop ARMED.")
        else:
            self.mapper.deactivate(arm.ee_pos, arm.ee_rpy)
            self.teleop_active = False
            logger.info("Teleop stopped. Arm holds its pose.")

    # -- threads ------------------------------------------------------------------
    def _tracker_loop(self):
        hz = 1.0 / max(self.control_hz, 1)
        while self.running.is_set():
            t0 = time.perf_counter()
            try:
                pose = self.sense.get_tracker_pose()
                if pose is not None:
                    with self._pose_lock:
                        self._latest_pose = pose
            except Exception as exc:
                logger.error("tracker read failed: %s", exc)
            rest = hz - (time.perf_counter() - t0)
            if rest > 0:
                time.sleep(rest)

    def _control_loop(self):
        hz = 1.0 / max(self.control_hz, 1)
        while self.running.is_set():
            t0 = time.perf_counter()
            try:
                self._tick()
            except Exception as exc:
                logger.error("control tick failed: %s", exc)
            rest = hz - (time.perf_counter() - t0)
            if rest > 0:
                time.sleep(rest)

    def _tick(self):
        """One control step; order matters and is copied from the original
        script — gripper coupling first, trigger, then EE command."""
        sense = self.sense.get_state()

        # gripper takes the sense encoder's value every tick, no trigger.
        if sense.encoder_rad is not None:
            mirror = getattr(self.gripper, "mirror_sense_encoder", None)
            if mirror is not None:
                mirror(sense.encoder_rad)
            else:
                self.gripper.send_position(ManualGripper.norm_rad(sense.encoder_rad))

        # tracker follows while (and only while) active
        if self.teleop_active:
            with self._pose_lock:
                pose = self._latest_pose
            if pose is not None:
                cmd = self.mapper.compute_cmd(pose.pos, pose.rpy)
                self.arm.send_ee_pose(cmd[0:3], cmd[3:6])

    def _diagnostic_loop(self):
        while self.running.is_set():
            time.sleep(1.0)
            try:
                arm = self.arm.get_state()
                gripper = self.gripper.get_state()
                with self._pose_lock:
                    pose = self._latest_pose
                logger.info(
                    "teleop=%s ee=%s joints=%s gripper=%.2f tracker=%s",
                    "ARMED" if self.teleop_active else "idle",
                    _fmt(arm.ee_pos or []),
                    _fmt(list(arm.joint_pos or [])[:3]),
                    gripper.position if gripper.position is not None else 0.0,
                    _fmt(list(pose.pos) if pose else []))
            except Exception as exc:
                logger.error("diag: %s", exc)


class ManualGripper:
    """When there's no sense encoder (ros backend), the gripper is driven
    from the session keyboard by nudging its setpoint."""

    @staticmethod
    def norm_rad(rad: float) -> float:
        # Empirical span of the pika sense twist encoder; tweak per machine
        # if your calibration differs.
        span = 1.6
        return max(0.0, min(1.0, rad / span))


def _fmt(vals):
    return "[" + ", ".join(f"{v:.3f}" for v in list(vals)[:3]) + "]"
