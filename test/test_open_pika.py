"""Unit tests that run without hardware and without lerobot."""
import sys
from pathlib import Path

# tests/folder -> src folder
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------- mapper — the safety-critical math
def test_mapper_relative_motion_maps_exactly():
    from open_pika.teleop.mapper import TrackerMapper

    m = TrackerMapper([0.0, 0.0, 0.0, 0.0, 1.5707963267948966, 0.0])
    m.activate([0.10, 0.00, 0.20], [0.0, 0.0, 0.0],
               [0.30, 0.05, 0.40], [0.0, 0.0, 0.0])
    # move the tracker +5 cm in y: arm command must move +5 cm in y too
    cmd = m.compute_cmd([0.10, 0.05, 0.20], [0.0, 0.0, 0.0])
    assert abs(cmd[0] - 0.30) < 1e-9
    assert abs(cmd[1] - 0.10) < 1e-9          # 0.05 + 0.05
    assert abs(cmd[2] - 0.40) < 1e-9


def test_mapper_rotation_is_propagated():
    import math
    from open_pika.teleop.mapper import TrackerMapper

    m = TrackerMapper([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    m.activate([0.1, 0.0, 0.2], [0.0, 0.0, 0.0],
               [0.3, 0.0, 0.4], [0.0, 0.0, 0.0])
    cmd = m.compute_cmd([0.1, 0.0, 0.2], [0.0, 0.0, math.pi / 4])
    assert abs(cmd[5] - math.pi / 4) < 1e-6   # yaw delta reaches the arm


def test_pose_valid_rejects_zero():
    from open_pika.teleop.mapper import TrackerMapper
    m = TrackerMapper([0.0] * 6)
    assert not m.pose_valid([0.0, 0.0, 0.0])
    assert m.pose_valid([0.0, 0.0, 0.01])


# ---------------------------------------------------------------- config
def test_config_defaults_and_validation():
    from open_pika.config import load_config
    cfg = load_config()
    assert cfg["backend"] in ("sdk", "ros", "mock")
    assert len(cfg["mapping"]["pika_to_arm"]) == 6


def test_config_rejects_bad_backend():
    from open_pika.config import load_config
    import pytest
    tmp = Path("/tmp/open_pika_test_cfg.yaml")
    tmp.write_text("backend: wrong\n")
    with pytest.raises(ValueError):
        load_config(tmp)


# ---------------------------------------------------------------- transform round-trips
def test_transform_round_trip():
    import math
    from open_pika.utils.transforms import mat_to_xyzrpy, xyzrpy_to_mat
    x, y, z, rx, ry, rz = 0.1, 0.2, 0.3, 0.1, 0.2, 0.3
    assert mat_to_xyzrpy(xyzrpy_to_mat(x, y, z, rx, ry, rz)) == \
        pytest_approx((x, y, z, rx, ry, rz))


def pytest_approx(vals):
    class approx_list(list):
        def __eq__(self, other):
            return all(abs(a - b) < 1e-9 for a, b in zip(self, other))
    return approx_list(vals)


# ---------------------------------------------------------------- quaternion round-trip
def test_quat_rpy_round_trip():
    import math
    from open_pika.utils.transforms import quat_from_rpy, rpy_from_quat
    rpy_in = (0.2, 0.1, 0.9)
    r, p, y = rpy_from_quat(*quat_from_rpy(*rpy_in))
    assert (abs(r - 0.2) < 1e-6 and abs(p - 0.1) < 1e-6
            and abs(y - 0.9) < 1e-6)


# ---------------------------------------------------------------- mock devices move
def test_mock_devices_sane_data():
    from open_pika.devices.mock import MockArm, MockCamera, MockGripper, MockSense
    arm = MockArm("a")
    st = arm.get_state()
    assert len(st.joint_pos) == 6 and all(-1 < v < 1 for v in st.joint_pos)

    sense = MockSense("s")
    pose = sense.get_tracker_pose()
    assert pose.valid

    gripper = MockGripper("g")
    gripper.send_position(0.8)
    assert gripper.get_state().position > 0.5

    cam = MockCamera("c", scene="checker", width=64, height=48)
    stamp, img = cam.read()
    assert img.shape == (48, 64, 3)


# ---------------------------------------------------------------- registry wiring
def test_registry_builds_mock_set():
    from open_pika.config import load_config
    from open_pika.devices import registry, shutdown
    cfg = load_config()
    dev = registry.build_devices(cfg, backend="mock", camera_ids=["realsense_head"])
    assert set(dev) >= {"arm", "gripper", "sense", "cameras"}
    assert [c.name for c in dev["cameras"]] == ["realsense_head"]
    shutdown(dev)


def test_registry_camera_filter():
    from open_pika.config import load_config
    from open_pika.devices import registry
    cfg = load_config()
    dev = registry.build_devices(cfg, backend="mock", camera_ids=None)
    assert len(dev["cameras"]) == 3


# ---------------------------------------------------------------- sessions scan
def test_datasets_scan_finds_lerobot_dir(tmp_path):
    from open_pika.session import datasets_scan
    (tmp_path / "mydata" / "meta").mkdir(parents=True)
    (tmp_path / "mydata" / "meta" / "info.json").write_text("{}")
    (tmp_path / "empty").mkdir()
    assert datasets_scan.find_datasets(tmp_path) == ["mydata"]
