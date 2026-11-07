"""
hardware_controller.py
Manages the sensors (PIR, LDR), actuators (MOSFET PWM, Relay), and Servo (via PCA9685).
Provides a clean interface for the decision engine.
"""
import logging
from gpiozero import DigitalInputDevice, DigitalOutputDevice
import RPi.GPIO as GPIO
try:
    from smbus2 import SMBus
    SMBUS_AVAILABLE = True
except ImportError:
    import smbus
    SMBUS_AVAILABLE = True
except Exception as e:
    SMBUS_AVAILABLE = False
    logging.warning(f"Could not load smbus/smbus2 for PCA9685: {e}")

import config
import time
import math

logger = logging.getLogger(__name__)

class PCA9685:
    """Minimal PCA9685 I2C driver for Servo control to avoid heavy dependencies."""
    def __init__(self, bus_number=1, address=0x40):
        self.address = address
        self.bus = None
        if SMBUS_AVAILABLE:
            try:
                try:
                    from smbus2 import SMBus
                    self.bus = SMBus(bus_number)
                except:
                    import smbus
                    self.bus = smbus.SMBus(bus_number)

                self._reset()
                self._set_pwm_freq(50) # 50Hz for typical servos
                logger.info(f"PCA9685 initialized at 0x{address:02X}")
            except Exception as e:
                logger.error(f"Failed to init PCA9685 at I2C bus {bus_number}: {e}")
                self.bus = None

    def _reset(self):
        if not self.bus: return
        self.bus.write_byte_data(self.address, 0x00, 0x00)

    def _set_pwm_freq(self, freq_hz):
        if not self.bus: return
        prescaleval = 25000000.0    # 25MHz
        prescaleval /= 4096.0       # 12-bit
        prescaleval /= float(freq_hz)
        prescaleval -= 1.0
        prescale = int(math.floor(prescaleval + 0.5))
        
        oldmode = self.bus.read_byte_data(self.address, 0x00)
        newmode = (oldmode & 0x7F) | 0x10    # sleep
        self.bus.write_byte_data(self.address, 0x00, newmode) # go to sleep
        self.bus.write_byte_data(self.address, 0xFE, prescale)
        self.bus.write_byte_data(self.address, 0x00, oldmode)
        time.sleep(0.005)
        self.bus.write_byte_data(self.address, 0x00, oldmode | 0x80)

    def set_pwm(self, channel, on, off):
        """Sets a single PWM channel"""
        if not self.bus: return
        try:
            self.bus.write_byte_data(self.address, 0x06 + 4*channel, on & 0xFF)
            self.bus.write_byte_data(self.address, 0x07 + 4*channel, on >> 8)
            self.bus.write_byte_data(self.address, 0x08 + 4*channel, off & 0xFF)
            self.bus.write_byte_data(self.address, 0x09 + 4*channel, off >> 8)
        except Exception as e:
            logger.error(f"PCA9685 I2C Write Error: {e}")

class HardwareController:
    def __init__(self):
        logger.info("Initializing Hardware Controller...")
        self.pir = None
        self.ldr = None
        self.pwm_mosfet = None
        self.relay1 = None
        self.relay2 = None
        self.servo_driver = None
        
        # Current state trackers
        self.current_duty_cycle = 0
        self.current_servo_angle = config.SERVO_DEFAULT_ANGLE

        self._setup_gpio()
        self._setup_i2c()
        
        # Move to default positions
        self.set_servo_angle(self.current_servo_angle)
        self.set_light_brightness(0)

    def _setup_gpio(self):
        try:
            # Use completely native RPi.GPIO for everything to stop library conflicts
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            
            # Inputs
            GPIO.setup(config.PIR_PIN, GPIO.IN)
            GPIO.setup(config.LDR_PIN, GPIO.IN)
            
            # MOSFET PWM
            GPIO.setup(config.PWM_MOSFET_PIN, GPIO.OUT)
            GPIO.output(config.PWM_MOSFET_PIN, GPIO.LOW)
            self.pwm_mosfet = GPIO.PWM(config.PWM_MOSFET_PIN, config.PWM_FREQ)
            self.pwm_mosfet.start(0)
            
            # Relays
            GPIO.setup(config.RELAY_CH1, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(config.RELAY_CH2, GPIO.OUT, initial=GPIO.LOW)
            
            logger.info("GPIO Initialized successfully using native RPi.GPIO.")
        except Exception as e:
            logger.error(f"GPIO Initialization failed: {e}")

    def _setup_i2c(self):
        self.servo_driver = PCA9685(address=config.PCA9685_ADDRESS)

    def is_motion_detected(self):
        try:
            return GPIO.input(config.PIR_PIN) == 1
        except:
            return False

    def is_dark(self):
        """
        Reads LM393 DO via native GPIO. 
        """
        try:
            state = GPIO.input(config.LDR_PIN)
            return state == config.LDR_DARK_VALUE
        except:
            return False

    def set_light_brightness(self, percentage):
        """Sets flood light brightness 0 - 100 via MOSFET and physically toggles the Relay to prevent floating gate leakage at 0%"""
        if 0 <= percentage <= 100:
            # Physical EMF / floating gate fix! 
            # If 0%, kill the relay to stop the ghost glow. If >0%, power the relay!
            self.toggle_relay(1, percentage > 0)
            
            if percentage != self.current_duty_cycle:
                if self.pwm_mosfet:
                    self.pwm_mosfet.ChangeDutyCycle(percentage)
                self.current_duty_cycle = percentage
        else:
            logger.warning("Brightness percentage must be between 0 and 100.")

    def set_day_night_mode(self, is_night):
        """
        Enforce strict power logic based on Day/Night sensor.
        During the day, relays go offline completely.
        During the night, IR LEDs are activated. Floodlight Relay is managed dynamically by brightness now.
        """
        if is_night:
            self.toggle_relay(2, True) # Power up IR LED Circuit
        else:
            self.toggle_relay(1, False) # Kill Floodlight Circuit
            self.toggle_relay(2, False) # Kill IR LED Circuit
            self.set_light_brightness(0)

    def set_servo_angle(self, angle):
        """Sets servo angle (0 to 180 degrees)"""
        angle = max(config.SERVO_MIN_ANGLE, min(config.SERVO_MAX_ANGLE, angle))
        self.current_servo_angle = angle
        
        if self.servo_driver:
            # Map angle to PWM pulse length
            # Standard servo limits: 500us to 2500us.
            # PCA9685 at 50Hz = 20,000us period. 4096 steps -> ~4.88us per step.
            # 500us / 4.88 = ~102.
            # 2500us / 4.88 = ~512.
            servo_min = 102 # Corrected Min pulse length
            servo_max = 512 # Corrected Max pulse length
            pulse = int((angle / 180.0) * (servo_max - servo_min) + servo_min)
            self.servo_driver.set_pwm(config.SERVO_CHANNEL, 0, pulse)

    def step_servo(self, increment):
        """Steps servo incrementally by increment degrees (+/-)"""
        new_angle = self.current_servo_angle + increment
        self.set_servo_angle(new_angle)

    def toggle_relay(self, channel, state):
        """
        # Toggles relay.
        # User confirmed relays are Active HIGH.
        # state=True means relay ON (so pin HIGH).
        """
        pin = config.RELAY_CH1 if channel == 1 else config.RELAY_CH2
        try:
            if state:
                GPIO.output(pin, GPIO.HIGH) # Active HIGH
            else:
                GPIO.output(pin, GPIO.LOW)  # Inactive LOW
        except Exception as e:
            logger.error(f"Relay toggle error: {e}")

    def cleanup(self):
        logger.info("Cleaning up hardware...")
        self.set_light_brightness(0)
        self.toggle_relay(1, False)
        self.toggle_relay(2, False)
        
        # Give the hardware a moment to process the zero-voltage PWM state before closing threads
        time.sleep(0.5)
        
        if self.pwm_mosfet: 
            # Force the pin physically low before releasing memory handle to prevent floating high states
            self.pwm_mosfet.stop()
            GPIO.setup(config.PWM_MOSFET_PIN, GPIO.OUT)
            GPIO.output(config.PWM_MOSFET_PIN, GPIO.LOW)
            self.pwm_mosfet = None
            
        # Relays: force off (HIGH) and then release
        GPIO.setup(config.RELAY_CH1, GPIO.OUT)
        GPIO.output(config.RELAY_CH1, GPIO.HIGH)
        GPIO.setup(config.RELAY_CH2, GPIO.OUT)
        GPIO.output(config.RELAY_CH2, GPIO.HIGH)
            
        if self.pir: self.pir.close()
        if self.ldr: self.ldr.close()
