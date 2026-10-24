"""open_pika command line.

    open_pika record    [--backend sdk|ros|mock] [--cameras a,b] [--root DIR]
    open_pika datasets  [--root DIR]           # what's on disk + sanity-ish
    open_pika cameras   [--backend ...]        # what the machine can see today

Flags are mirrors of the interactive answers, so nothing here is required.
"""
from __future__ import annotations

import argparse
import sys

from open_pika.session import interactive


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="open_pika",
        description="Piper arm teleoperation + LeRobot v3.0.0 dataset "
                    "recording.",
    )
    sub = p.add_subparsers(dest="command")

    rec = sub.add_parser("record", help="teleoperate + record a dataset")
    rec.add_argument("--backend", choices=["sdk", "ros", "mock"])
    rec.add_argument("--root", help="directory that holds datasets")
    rec.add_argument("--dataset", help="name; if exists it's resumed")
    rec.add_argument("--cameras", help="comma-separated camera list")
    rec.add_argument("--fps", type=int)
    rec.add_argument("--config", help="YAML config override")

    lists = sub.add_parser("datasets", help="list recorded datasets")
    lists.add_argument("--root", help="directory that holds datasets")

    cams = sub.add_parser("cameras", help="probe available cameras")
    cams.add_argument("--backend", choices=["sdk", "ros", "mock"])
    cams.add_argument("--config")

    return p


def main(argv=None) -> int:
    from open_pika.utils.log import setup_logging
    setup_logging()

    args = build_parser().parse_args(argv)

    if args.command == "record":
        from open_pika.session.interactive import RecordSession
        return RecordSession(args).run()

    if args.command == "datasets":
        from open_pika.session import datasets_scan
        root = args.root or interactive.DEFAULT_ROOT
        names = datasets_scan.find_datasets(root)
        if not names:
            print(f"No datasets found in {root}.")
            return 1
        print(f"Datasets in {root}:")
        for n in names:
            s = datasets_scan.dataset_summary(root, n)
            print(f"  {n}  episodes={s['episodes']} frames={s['frames']} "
                  f"fps={s['fps']}")
        return 0

    if args.command == "cameras":
        from open_pika.config import load_config
        cfg = load_config(args.config)
        backend = args.backend or cfg["backend"]
        from open_pika.session.interactive import _camera_choices
        for i, c in enumerate(_camera_choices(cfg, backend), 1):
            print(f"{i}. {c}")
        return 0

    build_parser().print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
