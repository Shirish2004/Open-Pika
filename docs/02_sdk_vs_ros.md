# SDK vs ROS backend

Same math, datasets and keyboards in both. The difference is purely transport:

| | `--backend sdk` | `--backend ros` |
|---|---|---|
| needs | `piper_sdk`, `pika` in python, no ROS | ROS 2 Humble + a workspace with `piper_ros` (+`sensor_tools` if you want IMU/gripper streams) |
| arm control | `C_PiperInterface_V2` EndPoseCtrl over CAN | `joint_ctrl_single` topic (joint space) |
| gripper | serial `pika.gripper` (encoder-mirror) | `/puppet/joint_left` index 6 / `data_msgs` |
| cameras | fisheye + D405 via pika SDK | any `sensor_msgs/Image` topic |
| end pose measurement | CAN feedback | `/puppet/end_pose_left` |
| best for | single-machine, low-latency teleop, home rigs | teams already running the ROS bring-up, sim/testing, plumbing other ROS nodes |

The ROS arm node talks joint commands, not end poses, so teleop in `ros`
backend uses measured joint feedback and `enable_flag`. If you want true EE
teleop via ROS, add an IK layer (e.g. pickplace or a small node that turns
end-poly goals to joints) — out of scope for now.

Running them side by side is fine and they don't need a topic of the other's
in-flight data — each backend is independent.
