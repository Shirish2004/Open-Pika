"""ROS backend bring-up.

Starts the piper_ros single-arm node. Recording/teleop itself runs in the
`open_pika --backend ros` CLI process (it only consumes these topics).
"""
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

import os


def generate_launch_description():
    piper_pkg = get_package_share_directory("piper_ros") \
        if "piper_ros" in _available_pkgs() else ""

    return LaunchDescription([
        DeclareLaunchArgument("can_port", default_value="can0"),
        DeclareLaunchArgument("arm_name", default_value="left"),

        Node(
            package="piper_ros",
            executable="piper_single_ctrl_node",
            name="piper_ctrl_single_left",
            namespace="/",
            output="screen",
            parameters=[{
                "piper_name": LaunchConfiguration("arm_name"),
                "can_port": LaunchConfiguration("can_port"),
            }],
        ) if piper_pkg else None
    ])


def _available_pkgs():
    try:
        from ament_index_python.packages import get_packages_with_prefixes
        return list(get_packages_with_prefixes().keys())
    except Exception:
        return []
