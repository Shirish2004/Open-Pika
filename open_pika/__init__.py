"""open_pika — teleoperate the AgileX Piper arm with a Pika Sense/Gripper rig,
and record the teleoperation directly to LeRobot v3.0.0 datasets.

The package is split in three layers that never leak into each other:

* ``open_pika.devices``  — hardware backends (``sdk``, ``ros``, ``mock``), one
  small adapter class per device per backend, all behind a common Protocol.
* ``open_pika.teleop``   — maps tracker poses to arm end-pose commands.
* ``open_pika.recording``— turns stamped device snapshots into LeRobot frames.
* ``open_pika.session``  — the interactive CLI that ties everything together.
"""

__all__ = ["__version__"]

from open_pika.version import __version__
