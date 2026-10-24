import os
from glob import glob
from setuptools import setup

package_name = "open_pika"


def find_packages(pkg_root=package_name):
    """Walk out the python packages (folders containing __init__.py)."""
    out = [pkg_root]
    for dirpath, dirnames, _ in os.walk(pkg_root):
        if os.path.isfile(os.path.join(dirpath, "__init__.py")):
            yield_dir = dirpath.replace(os.sep, ".")
            if yield_dir not in out:
                out.append(yield_dir)
    return out


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages",
            [os.path.join("resource", package_name)]),
        (os.path.join("share", package_name), ["package.xml"]),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
        (os.path.join("share", package_name, "launch"), glob("launch/*.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=False,
    maintainer="you",
    maintainer_email="you@example.com",
    description=(
        "Teleoperate the AgileX Piper arm with a Pika Sense + Pika Gripper "
        "rig and record LeRobot v3.0.0 datasets. SDK and ROS 2 "
        "backends are both first-class.",
    ),
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "open_pika = open_pika.cli:main",
        ],
    },
)
