# Hardware setup (SDK backend)

## what you need on this machine

| device | link | used by |
|---|---|---|
| Piper arm | CAN (socketcan `can0`) | `piper_sdk` |
| Pika Sense | USB serial (default `/dev/ttyUSB0`) | tracker, IMU, encoder, fisheye, D405 |
| Pika Gripper | USB serial (default `/dev/ttyUSB2`) | motor + fisheye |

## CAN bring-up (Piper)

```bash
sudo ip link set can0 down
sudo ip link set can0 up type can bitrate 1000000
```

Persist across boots with a `.link`/`.network` pair or a snap. The rig won't
do anything further until the arm answers on `can0`.

## serial ports — udev rules so they don't swap on reboot

USB serial numbers do shuffle; the two pika devices show up as
`/dev/ttyUSB*` in arbitrary order. Solutions that actually survive a reboot:

```bash
# /etc/udev/rules.d/99-pika.rules
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", \
  ATTRS{serial}=="<write-your pika sense serial>", \
  SYMLINK+="ttyPIKA_SENSE"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", \
  ATTRS{serial}=="<write-your gripper serial>", \
  SYMLINK+="ttyPIKA_GRIP"
```

Then `sudo udevadm control --reload-rules` and point
`~/.config/open_pika/config.yaml` at the stable symlinks.

## tracker pairing

The vive tracker ("WM0" in this workspace's script) has to be paired at the
base level before open_pika can find it: `pika`'s `Sense` object runs
pysurvive with the device string on `camera_cfg`. If you restart the base
station, wait a beat — device probe retries are built into the session.

## sanity checks

```bash
open_pika cameras --backend sdk     # what it can see
open_pika --help
```

If `can0` or the serial links aren't there — don't churn the config; fix the
device link first.
