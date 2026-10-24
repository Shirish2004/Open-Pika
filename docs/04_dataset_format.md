# Dataset format: what open_pika writes (lerobot v3.0.0)

We write through the official `lerobot` library (`LeRobotDataset`) with
`codebase_version = v3.0.0`. This doc pins our feature contract — the same
contract `open_pika.recording.frames.build_features` produces.

## non-camera features (parquet, per chunk, one row per tick)

| name | dtype | shape | meaning |
|---|---|---|---|
| `action` | float32 | (7,) | **next tick's** measured arm joints (rad ×6) + gripper normalised — 'action is where the arm ends up' |
| `observation.state` | float32 | (6,) | measured Piper joints at this tick (rad) |
| `observation.end_pose` | float32 | (6,) | measured ee xyz (m) + rpy (rad) at this tick |
| `observation.gripper` | float32 | (1,) | normalised opening, 0 closed .. 1 open |
| `observation.sense` | float32 | (7,) | sense twist encoder (rad) + imu acc (3) + gyro (3) |

Why action = next-tick measurement: with the SDK transport the arm is driven
in *end-pose space* (EndPoseCtrl), so exact commanded joints don't exist on
our side; measured-joint state at t+1 is the honest, transport-agnostic
action label. LeRobot examples conventionally work with this pair.

## camera features (mp4, per chunk, one per camera)

`observation.images.<camera name>` where camera names come from the selection
menu: `sense_fisheye`, `sense_realsense`, `gripper_fisheye`,
`gripper_realsense` (sdk backend), your `ros.image_topics` names (ros
backend), or the three mock scenes (mock backend).

## alignment

The `open_pika` pump ticks at exactly `recording.fps`. Images are the latest
frame of each camera at the tick (camera adapters keep only the newest one —
no history, no retries): that's the 'nearest in time' convention.

## training with it

`lerobot` datasets created this way load via LeRobotDataset and work with
`from_pretrained`-style pipelines and the lerobot-viz tooling; we do nothing
special on top, which is the point.
