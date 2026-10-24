"""Registry — turns (backend, config) into a ready set of device adapters.

This is the only place that knows which adapter class serves which backend,
so adding a backend (e.g. mock) or re-mapping topics stays one-file.
"""
from __future__ import annotations

from open_pika.utils.log import get_logger

logger = get_logger("registry")


def build_devices(cfg: dict, backend: str = None, camera_ids=None):
    """Return dict with arm/gripper/sense/cameras (list) for the backend.

    camera_ids restricts the camera list (interactive selection already
    happened); None means "everything the backend knows about".
    """
    backend = backend or cfg["backend"]

    if backend == "mock":
        return _mock_devices(cfg, camera_ids)
    if backend == "sdk":
        return _sdk_devices(cfg, camera_ids)
    if backend == "ros":
        return _ros_devices(cfg, camera_ids)
    raise ValueError(f"unknown backend '{backend}'")


# -- mock ---------------------------------------------------------------------
def _mock_devices(cfg, camera_ids):
    from open_pika.devices.mock import MockArm, MockCamera, MockGripper, MockSense

    cam = cfg["camera"]
    cameras = [_mock_cam(n, cam) for n in
               ("sense_fisheye", "gripper_fisheye", "realsense_head")]
    cameras = _filtercams(cameras, camera_ids)
    return {"arm": MockArm("piper_mock"), "gripper": MockGripper("gripper_mock"),
            "sense": MockSense("sense_mock"), "cameras": cameras}


def _mock_cam(name, cam, scene="checker"):
    from open_pika.devices.mock import MockCamera
    return MockCamera(name, scene=scene, width=cam["width"],
                      height=cam["height"], fps=cam["fps"])


# -- sdk ----------------------------------------------------------------------
def _sdk_devices(cfg, camera_ids):
    from open_pika.devices.arm_sdk import ArmSdk
    from open_pika.devices.gripper_sdk import GripperSdk
    from open_pika.devices.sense_sdk import SenseSdk
    from open_pika.devices.camera_sdk import SdkCamera

    sense = SenseSdk(cfg["sense"]["port"], cfg["sense"]["tracker_device"])
    gripper = GripperSdk(cfg["gripper"]["port"])
    arm = ArmSdk(cfg["arm"]["can_port"], cfg["arm"]["move_spd_rate"])

    camspec = cfg["camera"]

    def host_cam(host, prefix, pick_key):
        label = {"fisheye": f"{prefix}_fisheye", "realsense": f"{prefix}_realsense"}
        name = label[pick_key]
        if camera_ids is not None and name not in camera_ids:
            return None
        picker = getattr(host, f"get_{pick_key}_camera")
        cam = SdkCamera(name, host, picker, camspec["width"],
                        camspec["height"], camspec["fps"])
        return cam

    cameras = [c for c in (
        host_cam(sense, "sense", "fisheye"),
        host_cam(sense, "sense", "realsense"),
        host_cam(gripper, "gripper", "fisheye"),
        host_cam(gripper, "gripper", "realsense"),
    ) if c is not None]

    return {"arm": arm, "gripper": gripper, "sense": sense,
            "cameras": cameras}


# -- ros ----------------------------------------------------------------------
def _ros_devices(cfg, camera_ids):
    from open_pika.devices.ros_ipc import RosBridge

    bridge = RosBridge()
    arm_name = cfg.get("ros", {}).get("arm_name", "left")

    from open_pika.devices.arm_ros import ArmRos
    from open_pika.devices.gripper_ros import GripperRos
    from open_pika.devices.sense_ros import SenseRos
    from open_pika.devices.camera_ros import CameraRos

    arm = ArmRos(bridge, arm_name)
    gripper = GripperRos(bridge, arm_name)
    ros_cfg = cfg.get("ros", {})
    sense = SenseRos(bridge,
                     tracker_topic=ros_cfg.get("tracker_topic", ""),
                     imu_topic=ros_cfg.get("imu_topic", "/imu/data"))

    cameras = []
    for topic in ros_cfg.get("image_topics", []):
        if camera_ids is not None and topic not in camera_ids:
            continue
        cameras.append(CameraRos(bridge, topic))

    return {"arm": arm, "gripper": gripper, "sense": sense,
            "cameras": cameras, "bridge": bridge}


def _filtercams(cameras, ids):
    if ids is None:
        return cameras
    return [c for c in cameras if c.name in ids]


def shutdown(devices: dict) -> None:
    """Best-effort disconnect in reverse creation order; never raises."""
    for dev in reversed(list(devices.get("cameras", []))):
        _q(dev.disconnect)
    for key in ("gripper", "sense", "arm"):
        dev = devices.get(key)
        if dev is not None:
            _q(dev.disconnect)
    if devices.get("bridge"):
        devices["bridge"].shutdown()


def _q(fn) -> None:
    try:
        fn()
    except Exception as exc:
        logger.debug("disconnect hiccup: %s", exc)
