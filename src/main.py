ROBOT_LEFT_ADDRESS = "172.20.254.207"
ROBOT_RIGHT_ADDRESS = "172.20.254.208"
import logging

from robot_arm import RobotArm

logging.basicConfig(level=logging.INFO)

rl = RobotArm(ROBOT_LEFT_ADDRESS, name="left")
rl.connect()
rl.power_on()
rl.brake_release()

rr = RobotArm(ROBOT_RIGHT_ADDRESS, name="right")
rr.connect()
rr.power_on()
rr.brake_release()

rl.send_urscript_file("urscript/left_robot.script")
rr.send_urscript_file("urscript/right_robot.script")
