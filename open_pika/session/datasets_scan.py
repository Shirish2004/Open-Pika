"""Dataset listing helpers shared by the wizard and `open_pika datasets` CLI."""
from __future__ import annotations

import time
from pathlib import Path


def find_datasets(root: str | Path) -> list[str]:
    """Directory names under root that look like lerobot datasets (v2/v3)."""
    base = Path(root).expanduser()
    if not base.is_dir():
        return []
    out = []
    for child in sorted(base.iterdir()):
        meta = child / "meta"
        if (meta / "info.json").is_file() or (meta / "episodes.jsonl").is_file():
            out.append(child.name)
    return out


def dataset_summary(root: str | Path, name: str) -> dict:
    """episodes / frames / fps mined from meta files, best effort."""
    d = Path(root).expanduser() / name
    info = d / "meta" / "info.json"
    summary = {"name": name, "episodes": "?", "frames": "?", "fps": "?"}
    try:
        import json
        j = json.loads(info.read_text())
        summary.update({
            "episodes": j.get("total_episodes", "?"),
            "frames": j.get("total_frames", "?"),
            "fps": j.get("fps", "?"),
        })
    except Exception:
        pass
    return summary


def newest_episode_mtime(root: str | Path, name: str) -> float:
    d = Path(root).expanduser() / name
    last = 0.0
    for p in d.rglob("*"):
        try:
            last = max(last, p.stat().st_mtime)
        except OSError:
            pass
    return last or time.time()
