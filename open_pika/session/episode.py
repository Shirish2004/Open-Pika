"""One episode: pump feeding + recorder commit/discard around a keyboard loop."""
from __future__ import annotations

import threading
import time

from open_pika.recording.sync import DatasetPump
from open_pika.session.keyboard import KeyPoller, ask, ask_yes_no
from open_pika.utils.log import get_logger

logger = get_logger("episode")


class Episode:
    """Single recording unit; state machine lives in the session."""

    def __init__(self, index: int, task: str, pump: DatasetPump):
        self.index = index
        self.task = task
        self.pump = pump

    def run_interactive(self) -> str:
        """Drive one episode via keyboard.

        hotkeys:
          s   start
          e   end   (returns 'kept')
          d   discard only if recording hasn't started
          q   abort session
        returns 'kept' | 'discarded' | 'abort'
        """
        poll = KeyPoller()
        poll.start()
        try:
            print(f"\nep{self.index} task: '{self.task}'")
            print("  s = start recording   q = abort session")
            while True:
                k = poll.pop()
                if k == "s":
                    break
                if k in ("q", "\x03"):
                    return "abort"
                time.sleep(0.05)

            print("  recording... (e = end + keep episode, d = discard)")
            self.pump.start_episode(self.task)
            while True:
                k = poll.pop()
                if k == "e":
                    frames = self.pump.stop_episode()
                    idx = self.pump.recorder.save_episode()
                    print(f"  saved episode {idx} ({frames} frames).")
                    return "kept"
                if k == "d":
                    frames = self.pump.stop_episode()
                    self.pump.recorder.discard_episode()
                    print(f"  episode discarded ({frames} frames dropped).")
                    return "discarded"
                if k in ("q", "\x03"):
                    frames = self.pump.stop_episode()
                    self.pump.recorder.discard_episode()
                    return "abort"
                time.sleep(0.05)
        finally:
            poll.stop()
