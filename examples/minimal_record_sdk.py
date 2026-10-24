"""30-second sandbox tour: mock devices -> dataset on disk, zero hardware.

    /usr/bin/python examples/minimal_record_sdk.py
"""
from open_pika.config import load_config
from open_pika.devices import registry


def main():
    # mock backend: no arm, no gripper, no cameras needed
    cfg = load_config()
    cfg["backend"] = "mock"
    cfg["recording"]["fps"] = 10

    devices = registry.build_devices(cfg, backend="mock",
                                     camera_ids=["realsense_head"])
    for dev in (devices["sense"], devices["gripper"], devices["arm"],
                *devices["cameras"]):
        assert dev.connect(), dev.name

    # -- drive the arm around a bit while the recorder eats the stream -------
    from open_pika.recording.recorder_lerobot import LerobotRecorder
    from open_pika.recording.sync import DatasetPump
    import time

    rec = LerobotRecorder("/tmp/open_pika_demo", "sandbox", cfg["recording"]["fps"],
                          camera_names=[c.name for c in devices["cameras"]])
    rec.create()
    pump = DatasetPump(devices, rec, rec.fps)
    pump.start()

    arm = devices["arm"]
    print("episode: fake teleop for 3 s ...")
    pump.start_episode("sandbox episode: reach and grasp")
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 3.0:
        t = time.perf_counter() - t0
        arm.send_ee_pose([0.2 + 0.05 * t, 0.05, 0.3 - 0.05 * t],
                         [0.0, 0.0, 0.0])
        time.sleep(1.0 / cfg["control_hz"])
    print(f"{pump.stop_episode()} frames buffered")
    idx = rec.save_episode()
    pump.shutdown()

    arm_state = devices["arm"].get_state()
    print("final arm state:", arm_state)
    registry.shutdown(devices)
    print(f"\nDataset written: /tmp/open_pika_demo/sandbox episode {idx}")


if __name__ == "__main__":
    main()
