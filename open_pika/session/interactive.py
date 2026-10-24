"""The interactive recording wizard + session loop.

Answers to all questions also exist as CLI flags (see cli/main.py), so a
seasoned user can one-line this; the wizard below exists for humans and for
the first run on a new machine.
"""
from __future__ import annotations

import datetime
import os
import sys
import time

from open_pika.config import load_config
from open_pika.devices import registry
from open_pika.recording.recorder_lerobot import LerobotRecorder
from open_pika.recording.sync import DatasetPump
from open_pika.session import datasets_scan
from open_pika.session.keyboard import ask, ask_yes_no, pause
from open_pika.session.episode import Episode
from open_pika.teleop.controller import TeleopController
from open_pika.utils.log import get_logger

logger = get_logger("session")

DEFAULT_ROOT = "~/open_pika_datasets"


def _flag(args, key, default=None):
    return getattr(args, key, default) if args else default


class RecordSession:
    """Sequence: wizard → connect → episodes loop → graceful shutdown."""

    def __init__(self, args=None):
        self.args = args
        self.cfg = None
        self.devices = None
        self.controller = None
        self.pump = None
        self.recorder = None
        self.stopped = False

    # ------------------------------------------------------------------ entry
    def run(self) -> int:
        self.cfg = load_config(_flag(self.args, "config"))
        if _flag(self.args, "backend"):
            self.cfg["backend"] = _flag(self.args, "backend")
        backend = self.cfg["backend"]

        print(f"\n=== open_pika recording session (backend: {backend}) ===\n")

        # 1. storage
        root = ask("Directory where datasets live", args_default(
            self.args, "root", DEFAULT_ROOT))
        # 2. dataset: resume existing?
        name = self._choose_dataset(root)
        fps = int(ask("Dataset fps", str(self.cfg["recording"]["fps"])))
        self.cfg["recording"]["fps"] = fps

        # 3. cameras
        cams = self._select_cameras(backend)

        # 4. connect the device set
        self.devices = registry.build_devices(self.cfg, backend, camera_ids=cams)
        if not self._connect_devices():
            return 1

        # 5. recorder + pump + teleop
        self.recorder = self._open_recorder(root, name)
        self.pump = DatasetPump(self.devices, self.recorder, fps)
        self.pump.start()
        self.controller = TeleopController(self.devices, self.cfg)
        if not self.devices_ready():
            return 1
        self.controller.start()

        # 6. episodes
        self._episode_loop(root, name)

        # 7. wind down
        self._shutdown()
        return 0

    # ------------------------------------------------------------ wizard bits
    def _choose_dataset(self, root):

        existing = datasets_scan.find_datasets(root)

        if existing and ask_yes_no(
                f"Found {len(existing)} dataset(s) in {root}. Resume one?",
                default=True):
            for i, nm in enumerate(existing):
                print(f"  {i + 1}. {nm}")
            pick = ask("Which one (1-{})".format(len(existing)), "1")
            idx = int(pick if pick.isdigit() else 1) - 1
            name = existing[max(idx, 0)]
            s = datasets_scan.dataset_summary(root, name)
            print(f"  -> resuming {name} ({s['episodes']} episodes)")
            return name
        print("  (continuing with a fresh dataset)")
        default_name = datetime.datetime.now().strftime("run_%Y%m%d_%H%M%S")
        name = ask("New dataset name", default_name)
        if datasets_scan.find_datasets(root).count(name):
            if not ask_yes_no(f"{name} already exists - continue appending "
                              "the next episode?"):
                name = ask("New dataset name", default_name + "_b")
        return name

    def _select_cameras(self, backend):
        choices = _camera_choices(self.cfg, backend)
        if not choices:
            return []
        print("\nAvailable cameras:")
        for i, c in enumerate(choices):
            print(f"  {i + 1}. {c}")
        raw = ask("Use which cameras? (comma numbers, 'a' = all)", "a")
        if raw.strip().lower() in ("a", ""):
            return choices
        picked = []
        for tok in raw.replace(" ", "").split(","):
            if tok.isdigit() and 1 <= int(tok) <= len(choices):
                picked.append(choices[int(tok) - 1])
        return picked or choices

    # ------------------------------------------------------------ device setup
    def _connect_devices(self) -> bool:
        for key in ("sense", "gripper", "arm"):
            dev = self.devices.get(key)
            if dev is None:
                continue
            print(f"  connecting {key} ({dev.describe()})")
            if not try_connect(dev):
                print(f"  ! {key} connect failed. Check ports / CAN and try "
                      "again, or use --backend mock to exercise the pipeline "
                      "in sandbox mode.")
                registry.shutdown(self.devices)
                return False
        for cam in self.devices.get("cameras", []):
            if not try_connect(cam):
                print(f"  ! camera '{cam.name}' failed (empty is fine, frameless)")
        return True

    def _open_recorder(self, root, name) -> LerobotRecorder:
        fps = self.cfg["recording"]["fps"]
        exists = datasets_scan.find_datasets(root).count(name) > 0
        if exists:
            return LerobotRecorder.open(root, name, fps)
        rec = LerobotRecorder(root, name, fps,
                              camera_names=[c.name for c in
                                            self.devices["cameras"]])
        rec.create()
        return rec

    def devices_ready(self) -> bool:
        has_tracker = len(self.devices["sense"].get_tracker_devices()) > 0
        if not has_tracker:
            print("\nNo tracker device found — teleop will idle. If you meant "
                  "to drive by hand, use --backend mock, or run teleop with "
                  "the pika connected.")
        return True

    # --------------------------------------------------------------- episodes
    def _episode_loop(self, root, name):
        instructions = []
        n = self.recorder.episode_count()
        print(f"\nDataset {root}/{name} — {n} episodes so far.")
        if not self.controller.wait_for_tracker():
            print("No tracker; jogging keys disabled. Ctrl-C exits.")

        while not self.stopped:
            task = ask("'task' instruction for this episode", "")
            if not task:
                print("  instruction can't be empty.")
                continue
            instructions.append(task)

            ep = Episode(n, task, self.pump)
            outcome = ep.run_interactive()
            n = self.recorder.episode_count()

            if outcome == "abort":
                self.stopped = True
                break
            print(f"\n  dataset now has {n} episodes -> {root}/{name}")
            if not ask_yes_no("Continue to next episode?", default=True):
                break

    # ------------------------------------------------------------------ teardown
    def _shutdown(self):
        print("\nShutting down...")
        if self.pump:
            self.pump.stop_episode()
            self.pump.shutdown()
        if self.controller:
            self.controller.set_teleop(False)
            self.controller.stop()
        if self.devices:
            registry.shutdown(self.devices)
        print("Done.")


def try_connect(dev) -> bool:
    try:
        return bool(dev.connect())
    except Exception as exc:
        logger.error("%s connect crashed: %s", getattr(dev, "name", dev), exc)
        return False


def args_default(args, key, default):
    return _flag(args, key, default) or default


def _camera_choices(cfg, backend) -> list[str]:
    """Plan-time list of camera ids per backend (plan-time; real adapters connect
    later and may fail individually)."""
    if backend == "mock":
        return ["sense_fisheye", "gripper_fisheye", "realsense_head"]
    if backend == "sdk":
        return ["sense_fisheye", "sense_realsense",
                "gripper_fisheye", "gripper_realsense"]
    if backend == "ros":
        return list(cfg.get("ros", {}).get("image_topics", []))
    return []
