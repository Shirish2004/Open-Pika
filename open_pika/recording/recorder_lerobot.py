"""LeRobot v3.0.0 dataset writer — the *only* file that talks to lerobot.

Every lerobot API quirk (import paths, create() kwargs, video encoders) stays
behind this class. If lerobot renames things across releases, this is the
one file to fix.
"""
from __future__ import annotations

import json
from pathlib import Path

from open_pika.utils.log import get_logger

logger = get_logger("recorder")


def _import_dataset_class():
    """Handle lerobot's package layout changes across versions."""
    try:
        from lerobot.datasets.lerobot_dataset import LeRobotDataset
        return LeRobotDataset
    except ImportError:
        from lerobot.common.datasets.lerobot_dataset import LeRobotDataset
        return LeRobotDataset


class LerobotRecorder:
    """Writes one dataset: N episodes, chosen cameras, configurable root."""

    def __init__(self, root: str, name: str, fps: int, camera_names=None):
        self.root = Path(root).expanduser()
        self.name = name
        self.fps = fps
        self.camera_names = list(camera_names or [])
        self.dataset = None
        self._episode_task = ""

    # -- dataset lifecycle -------------------------------------------------------
    def create(self) -> None:
        """Fresh dataset at 'root/name'."""
        from open_pika.recording.frames import build_features

        LeRobotDataset = _import_dataset_class()
        repo_id = str(self.root / self.name)
        features = build_features(self.camera_names)

        # create() signature drifted between lerobot releases; try the
        # richest call first and shed kwargs on failure.
        attempts = (
            dict(features=features, use_videos=True, robot_type="pika_piper"),
            dict(features=features, use_videos=True),
        )
        for kwargs in attempts:
            try:
                self.dataset = LeRobotDataset.create(repo_id=repo_id,
                                                     fps=self.fps, **kwargs)
                break
            except TypeError as exc:
                logger.debug("create(%s) rejected: %s", kwargs, exc)
        else:
            raise RuntimeError(
                f"LeRobotDataset.create is not compatible with the installed "
                f"lerobot — see docs/04_dataset_format.md")

        logger.info("Dataset '%s' created (fps=%d, cameras=%s).",
                    repo_id, self.fps, self.camera_names or "none")

    @classmethod
    def open(cls, root: str, name: str, fps: int) -> "LerobotRecorder":
        """Resume an existing dataset; new frames append as later episodes."""
        LeRobotDataset = _import_dataset_class()
        rec = cls(root, name, fps,
                  camera_names=_camera_names_from_meta(_load_meta(root, name)))
        rec.dataset = LeRobotDataset(str(Path(root).expanduser() / name))
        logger.info("Resumed '%s' — %d existing episode(s).",
                    name, rec.episode_count())
        return rec

    # -- frames / episodes ---------------------------------------------------------
    def add_frame(self, frame: dict, task: str) -> None:
        self._episode_task = task
        self.dataset.add_frame(frame=frame, task=task)

    def save_episode(self) -> int:
        self.dataset.save_episode(task=self._episode_task)
        idx = self.episode_count() - 1
        logger.info("Episode %d committed (%s).", idx, self._episode_task)
        return idx

    def discard_episode(self) -> None:
        """Drop the currently buffered, uncommitted episode."""
        clear = getattr(self.dataset, "clear_episode_buffer", None)
        if clear is not None:
            clear()
            logger.info("Buffered episode discarded.")
            return
        # Newer lerobot dropped clear_episode_buffer: commit to disk, then
        # delete — guaranteed same net effect.
        idx = self.save_episode()
        self.delete_episode(idx)

    def delete_episode(self, index: int) -> None:
        del_ep = getattr(self.dataset, "delete_episode", None)
        if del_ep is None:
            raise RuntimeError(
                "Installed lerobot can't delete episodes; remove the dataset "
                "directory manually or use a fresh dataset.")
        del_ep(index)

    def episode_count(self) -> int:
        return self.dataset.meta.total_episodes


def _load_meta(root, name) -> dict:
    """Small dict from existing metadata, used pre-open for camera names."""
    meta = Path(root).expanduser() / name / "meta"
    info = meta / "info.json"
    if info.is_file():
        return json.loads(info.read_text())
    return {}


def _camera_names_from_meta(meta: dict) -> list:
    features = meta.get("features", {})
    return [k.split(".", 2)[2] for k in features
            if k.startswith("observation.images.")]
