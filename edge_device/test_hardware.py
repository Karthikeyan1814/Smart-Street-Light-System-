import logging
import time

from hardware_controller import HardwareController


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_hardware")


def main() -> None:
  hw = HardwareController()

  try:
    logger.info("Testing LED brightness: 0%% -> 50%% -> 100%%")
    for value in [0.0, 0.5, 1.0]:
      hw.set_light_brightness(value * 100.0)
      time.sleep(1.0)

    logger.info("Testing servo sweep: 0° -> 90° -> 180° -> 90°")
    sequence = [0, 90, 180, 90]
    step_delay = 0.05

    current_angle = sequence[0]
    hw.set_servo_angle(current_angle)
    time.sleep(0.5)

    for target in sequence[1:]:
      step = 5 if target > current_angle else -5
      for angle in range(current_angle, target + step, step):
        hw.set_servo_angle(angle)
        time.sleep(step_delay)
      current_angle = target
      time.sleep(0.5)

    logger.info("Hardware test completed.")
  finally:
    hw.cleanup()


if __name__ == "__main__":
  main()