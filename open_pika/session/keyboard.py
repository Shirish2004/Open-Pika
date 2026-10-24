"""Terminal keyboard listener without external deps.

Standard termios+select trick: when armed, the terminal is flipped to raw
mode for a moment so we can poll without echo, and always restored on exit
in a handler, so ^C can't leave the user's shell state broken.
"""
from __future__ import annotations

import select
import sys
import termios
import tty
import threading


class KeyPoller(threading.Thread):
    """Non-blocking key sniffer. `key` property holds the latest press."""

    def __init__(self, prompt=""):
        super().__init__(daemon=True, name="keypoller")
        self.prompt = prompt
        self.key = None
        self._lock = threading.Lock()
        self._stop = threading.Event()

    def run(self):
        fd = sys.stdin.fileno()
        old = None
        try:
            old = termios.tcgetattr(fd)
            tty.setcbreak(fd)
        except Exception:
            return  # not a tty (target: pipes/CI) — poller does nothing

        try:
            while not self._stop.is_set():
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch = sys.stdin.read(1)
                    with self._lock:
                        self.key = ch
        finally:
            if old is not None:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def pop(self) -> str | None:
        """Consumes the last key pressed (None otherwise)."""
        with self._lock:
            key, self.key = self.key, None
            return key

    def stop(self) -> None:
        self._stop.set()
        self.join(timeout=2)


def pause(text: str = "") -> None:
    """Blocking 'press enter' pause, prints an empty line."""
    input(f"{text}\npress ENTER to continue... ".rstrip())


def ask(prompt: str, default: str = "") -> str:
    """input() with a default, never raises on EOF."""
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        val = ''
    return val or default


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        a = ask(f"{prompt} ({hint})", "y" if default else "n").lower()
        if a in ("y", "yes", "1", "true"):
            return True
        if a in ("n", "no", "0", "false"):
            return False
        print("  please answer y or n.")
