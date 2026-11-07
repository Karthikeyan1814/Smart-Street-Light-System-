import logging
from typing import Optional

from config import RUN_ON_RPI

logger = logging.getLogger(__name__)

try:
    if RUN_ON_RPI:
        import RPi.GPIO as GPIO  # type: ignore
    else:
        GPIO = None  # type: ignore
except Exception:  # pragma: no cover - non-RPi environments
    GPIO = None  # type: ignore


LED_PIN = 18
SERVO_PIN = 17


class HardwareController:
    """
    Abstracts LED brightness and servo angle control.

    On Raspberry Pi, uses PWM via RPi.GPIO; on other platforms, it logs
    the intended actions for simulation.
    """

    def __init__(self) -> None:
        self._pwm_led: Optional["GPIO.PWM"] = None
        self._pwm_servo: Optional["GPIO.PWM"] = None
        if GPIO is not None:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(LED_PIN, GPIO.OUT)
            GPIO.setup(SERVO_PIN, GPIO.OUT)
            self._pwm_led = GPIO.PWM(LED_PIN, 1000)
            self._pwm_servo = GPIO.PWM(SERVO_PIN, 50)
            self._pwm_led.start(0)
            self._pwm_servo.start(7.5)
            logger.info("HardwareController initialized with real GPIO.")
        else:
            logger.info("HardwareController running in simulated mode (no GPIO).")

    def set_led_brightness(self, brightness: int) -> None:
        brightness = max(0, min(100, brightness))
        if self._pwm_led is not None:
            self._pwm_led.ChangeDutyCycle(brightness)
        logger.info("[Hardware] LED brightness -> %d%%", brightness)

    def set_servo_angle(self, angle: int) -> None:
        angle = max(0, min(180, angle))
        if self._pwm_servo is not None:
            duty = 2.5 + (angle / 180.0) * 10.0
            self._pwm_servo.ChangeDutyCycle(duty)
        logger.info("[Hardware] Servo angle -> %d degrees", angle)

    def cleanup(self) -> None:
        if self._pwm_led is not None:
            self._pwm_led.stop()
        if self._pwm_servo is not None:
            self._pwm_servo.stop()
        if GPIO is not None:
            GPIO.cleanup()
        logger.info("HardwareController cleaned up.")


