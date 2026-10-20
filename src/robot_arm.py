"""For Universal Robot robot arm control"""

import logging
import os
import re
import socket
import textwrap
import time
from typing import TextIO


class RobotArm:
    def __init__(
        self,
        ip_address: str = "localhost",
        dashboard_port: int = 29999,
        urscript_port: int = 30002,
        name: str = "robot",
    ) -> None:
        self.ip_address: str = ip_address
        self.dashboard_port: int = dashboard_port
        self.urscript_port: int = urscript_port
        self._sock_dashboard: socket.socket | None = None
        self._sock_urscript: socket.socket | None = None
        self._reader_dashboard: TextIO | None = None
        self.name: str = name if name else "robot"
        self._log = logging.getLogger(f"robot.{name}")

    def connect(self) -> None:
        self._log.info("Connecting to robot at %s", self.ip_address)
        self._sock_dashboard = socket.create_connection(
            (self.ip_address, self.dashboard_port)
        )
        self._reader_dashboard = self._sock_dashboard.makefile(
            "r", encoding="ascii", newline="\n"
        )
        _ = self.read_line_dashboard()  # consume welcome message

        self._sock_urscript = socket.create_connection(
            (self.ip_address, self.urscript_port)
        )
        self._log.info("Connected to robot")

    def disconnect(self) -> None:
        if self._reader_dashboard:
            self._reader_dashboard.close()
        if self._sock_dashboard:
            self._sock_dashboard.close()
        if self._sock_urscript:
            self._sock_urscript.close()
        self._log.info("Disconnected from robot")

    @property
    def connected(self) -> bool:
        return self._sock_dashboard is not None and self._sock_urscript is not None

    def send_dashboard(self, command: str) -> None:
        self._log.debug("Dashboard command: %s", command.strip())
        self._sock_dashboard.sendall(command.encode("ascii"))

    def read_line_dashboard(self) -> str:
        line = self._reader_dashboard.readline().rstrip("\r\n")
        self._log.debug("Dashboard reply: %s", line)
        return line

    def send_urscript(self, program: str, program_name: str = "program") -> None:
        placeholder = "__GRIPPER_BOX_ADDR__"
        if placeholder in program:
            ip_parts = self.ip_address.split(".")
            last_octet = int(ip_parts[-1])
            gripper_box_ip = (
                "localhost"
                if last_octet % 2
                else ".".join((*ip_parts[:-1], str(last_octet - 100)))
            )
            self._log.info("Replacing %s with %s", placeholder, gripper_box_ip)
            program = program.replace(placeholder, gripper_box_ip)

        stripped = program.strip()
        if not stripped.startswith("def ") and not stripped.endswith("end"):
            self._log.info("Wrapping URScript in def %s(): ... end", program_name)
            indented_program = textwrap.indent(stripped, "    ")
            program = f"def {program_name}():\n{indented_program}\nend\n"
        self._log.info("Sending URScript (%d characters)", len(program))
        self._sock_urscript.sendall(program.encode("utf-8"))

    def send_urscript_file(self, path: str, program_name: str | None = None) -> None:
        self._log.info("Loading URScript file: %s", path)
        if program_name is None:
            # URScript identifiers cannot contain e.g. hyphens. E.g., `pick-and-place` becomes `pick_and_place`
            program_name = re.sub(
                r"\W", "_", os.path.splitext(os.path.basename(path))[0]
            )
        with open(path, "r") as f:
            self.send_urscript(f.read() + "\n", program_name)

    def robot_mode(self) -> str:
        self.send_dashboard("robotmode\n")
        return self.read_line_dashboard()

    def program_running(self) -> bool:
        self.send_dashboard("running\n")
        return self.read_line_dashboard() == "Program running: true"

    def is_remote_control(self) -> bool:
        self.send_dashboard("is in remote control\n")
        return self.read_line_dashboard() == "true"

    def is_protective_stopped(self) -> bool:
        self.send_dashboard("is protective stopped\n")
        return self.read_line_dashboard() == "true"

    def check_ready(self) -> None:
        if not self.is_remote_control():
            self._log.error("Robot is not in remote control mode")
            raise RuntimeError(
                "Robot is not in remote control mode. Switch the teach pendant to REMOTE."
            )

        if self.is_protective_stopped():
            self._log.error("Robot is in protective stop")
            raise RuntimeError(
                "Robot is in protective stop. Clear it on the teach pendant first."
            )

        self._log.info("Robot is in remote control and not in protective stop")

    def power_on(self) -> None:
        mode = self.robot_mode()
        if mode != "Robotmode: POWER_OFF":
            self._log.info("Robot is already powered on (%s), skipping", mode)
            return

        self.check_ready()
        self._log.info("Powering on robot...")
        self.send_dashboard("power on\n")
        _ = self.read_line_dashboard()  # consume
        while self.robot_mode() != "Robotmode: IDLE":
            self._log.info("Waiting for robot to power on...")
            time.sleep(1)
        self._log.info("Robot is powered on (IDLE)")

    def brake_release(self) -> None:
        if self.robot_mode() == "Robotmode: RUNNING":
            self._log.info("Brakes already released, skipping")
            return

        self.check_ready()
        self._log.info("Releasing brakes...")
        self.send_dashboard("brake release\n")
        _ = self.read_line_dashboard()  # consume
        while self.robot_mode() != "Robotmode: RUNNING":
            self._log.info("Waiting for brakes to release...")
            time.sleep(1)
        self._log.info("Brakes released (RUNNING)")
