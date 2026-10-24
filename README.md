# open_pika

**Teleoperate the [AgileX Piper](https://global.agilex.ai/) arm with a [Pika
Sense + Pika Gripper](https://global.agilex.ai/Products/detail/id/99.html) rig —
and record everything straight to
[LeRobot v3.0.0](https://github.com/huggingface/lerobot) datasets.**

```
   your hand (tracker)  ─►  open_pika  ─►  Piper arm  ─►  your dataset,
        sense encoder  ─►             ─►  gripper       episode by episode
        fisheye/D405   ─►             ─►  cameras       ready for imitation
```

## Why

The vendor worlds give you two half-answers: the pika SDK talks hardware but
writes CSV frames, and piper ROS talks topics but knows nothing about
imitation-learning formats. `open_pika` glues the two halves together:

* **Two interchangeable backends** — `--backend sdk` (direct CAN/serial,
  lowest latency, no ROS needed) or `--backend ros` (the rig, over topics:
  piper_ros + sensor_tools). Same teleop math, same datasets from either.
* **Interactive but scriptable** — pick storage location, dataset (resume or
  new), cameras, fps, per-episode task instructions; everything duplicates as
  CLI flags, so day 1 is a wizard and day 100 is a cron job.
* **Real recording** — LeRobot v3.0.0 via the official `lerobot` library;
  episodes with tasks, chunked parquet state, mp4 video, documentary-grade
  metadata. Train with any `.from_local`-capable pipeline afterwards.

## Install

Screenshots of a session and hardware notes live in `docs/`.

```bash
# ROS 2 Humble is expected for the ros backend; the sdk backend needs none.
git clone https://github.com/Shirish2004/Open-Pika.git
cd open_pika
/usr/bin/python -m pip install -r requirements.txt   # lerobot is the big one
colcon build --packages-select open_pika && source install/setup.bash
```

Recommended (keeps your ROS numpy happy):

```bash
python3 -m virtualenv --system-site-packages ~/.venvs/open_pika
~/.venvs/open_pika/bin/pip install "numpy<2" lerobot
```

## Quick start (no hardware!)

```bash
open_pika record --backend mock           # full pipeline on synthetic data
open_pika datasets --root ~/open_pika_datasets
```

On a real rig:

```bash
open_pika record --backend sdk            # everything via the inner loop in `sdk/`
open_pika record --backend ros            # topics & piper launch files instead
```

## What you can drive from the keyboard

| key | effect (in a running session) |
|-----|-------------------------------|
| `s` | start recording the current episode |
| `e` | end it, save it |
| `d` | discard the take and re-do |
| `q` | wind the whole session down |

`n`/`y` are used for the per-episode task instruction prompt (typed freely,
becomes the episode's task metadata in the dataset).

## Data recorded per timestep

| feature | shape | note |
|---|---|---|
| `action` | (7,) | joint position targets + gripper open/close normalised |
| `observation.state` | (6,) | measured piper joint angles (rad) |
| `observation.end_pose` | (6,) | measured end pose xyz (m) + rpy (rad) |
| `observation.gripper` | (1,) | normalised gripper opening |
| `observation.sense` | (7,) | sense encoder + IMU acc/gyr |
| `observation.images.<cam>` | mp4 | any camera you picked, from any backend |

## Repo layout

```
open_pika/
├── open_pika/
│   ├── devices/     adapters: sdk (CAN/serial) · ros (topics) · mock (sandbox)
│   ├── teleop/      tracker->arm math, 50 Hz controller
│   ├── recording/   features, dataset pump, lerobot writer (v3.0.0)
│   ├── session/     interactive wizard, episode loop, keybindings
│   └── cli/         the open_pika entry point
├── config/          default.yaml — ports, serials, topics, mapping consts
├── launch/          ros-backend bring-up
├── examples/        minimal 30-line sandbox recording demo
└── docs/            hardware setup, backend comparison, dataset format
```

## Requirements

* Linux (Ubuntu 22.04), Python 3.10
* piper_sdk + pika (AgileX SDKs, referenced as local paths or pip)
* lerobot (`pip install lerobot`)
* For `--backend ros`: ROS 2 Humble with piper_ros built in a workspace

## License

Apache-2.0.
