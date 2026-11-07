import logging
import time
from hardware_controller import HardwareController

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_relays")

def main() -> None:
    hw = HardwareController()

    try:
        logger.info("--- Testing Relay CH1 (Main Light) ---")
        hw.toggle_relay(1, True)
        time.sleep(2)
        hw.toggle_relay(1, False)
        time.sleep(1)

        logger.info("--- Testing Relay CH2 (Indicator) ---")
        hw.toggle_relay(2, True)
        time.sleep(2)
        hw.toggle_relay(2, False)
        time.sleep(1)

        logger.info("--- Testing Both Relays ---")
        hw.toggle_relay(1, True)
        hw.toggle_relay(2, True)
        time.sleep(2)
        hw.toggle_relay(1, False)
        hw.toggle_relay(2, False)
        time.sleep(2)

        logger.info("Relay test completed successfully.")
    finally:
        hw.cleanup()

if __name__ == "__main__":
    main()
