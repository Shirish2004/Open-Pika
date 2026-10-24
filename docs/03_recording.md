# Recording with the interactive wizard

`open_pika record` (no args) walks through it. Every question has a CLI
dup, for cron/scripted usage.

## how the wizard goes through

```
Directory where datasets live [~/open_pika_datasets]:
Found 2 dataset(s) in /home/you/open_pika_datasets. Resume one? (Y/n)
  1. run_20260103_110324
  2. run_20260103_114022
Which one (1-2): 2
Dataset fps [30]:
Available cameras:
  1. sense_fisheye
  2. sense_realsense
  3. gripper_fisheye
  4. gripper_realsense
Use which cameras? (comma numbers, 'a' = all) [a]: 1,3
```

* **resume** — picking an existing dataset opens it; episodic appends
  continue at the last episode index. Nothing is overwritten.
* **cameras** — the camera menu is just the plan for this session; if one
  of them fails to connect (bad D405 serial etc.) the session goes on
  without that stream, and only that camera's mp4 stays empty.
* **task instruction** — free text, becomes the episode's `task` metadata;
  typical for imitation pipelines that condition on the phrase.

## per-episode keyboard

```
ep3 task: 'pick the red cube'
  s = start recording   q = abort session
  recording... (e = end + keep episode, d = discard)
```

* `d` only works after the take started; it clears lerobot's episode buffer
  (or commits+deletes on lerobot builds where the buffer API is gone).
* `Ctrl-C` at any point unwinds devices and dataset cleanly, no half-written
  episodes.

## continuing episodes

Ending one episode spits out the new episode count and hands you right back
to the "next episode?" prompt — keep typing instructions and takes as long
as the rig tolerates it; everything lands in one lerobot dataset in chunked
v3 files.

## storage layout (what lerobot writes)

```
root/
└── <dataset name>/
    ├── meta/info.json + episodes.jsonl ...
    ├── data/chunk-0/episode_*.parquet
    └── videos/chunk-0/<camera>/episode_*.mp4
```

`open_pika datasets --root ~/open_pika_datasets` summarises it (episodes /
frames / fps) without opening lerobot.
