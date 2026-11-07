import time
import sys

try:
    from smbus2 import SMBus
except ImportError:
    from smbus import SMBus

# Basic PCA9685 Controller for direct calibration
class SimplePCA9685:
    def __init__(self, address=0x40):
        self.bus = SMBus(1)
        self.address = address
        self.bus.write_byte_data(self.address, 0x00, 0x00) # Reset
        time.sleep(0.05)
        # Set frequency to 50Hz
        prescale_val = int(25000000.0 / 4096.0 / 50.0 - 0.5)
        
        old_mode = self.bus.read_byte_data(self.address, 0x00)
        self.bus.write_byte_data(self.address, 0x00, (old_mode & 0x7F) | 0x10) # Sleep
        self.bus.write_byte_data(self.address, 0xFE, prescale_val) # Set prescale
        self.bus.write_byte_data(self.address, 0x00, old_mode) # Wake
        time.sleep(0.005)
        self.bus.write_byte_data(self.address, 0x00, old_mode | 0xa1) # Auto-increment
        print("PCA9685 Initialized at 50Hz.")

    def set_pwm(self, channel, on, off):
        self.bus.write_byte_data(self.address, 0x06 + 4 * channel, on & 0xFF)
        self.bus.write_byte_data(self.address, 0x07 + 4 * channel, on >> 8)
        self.bus.write_byte_data(self.address, 0x08 + 4 * channel, off & 0xFF)
        self.bus.write_byte_data(self.address, 0x09 + 4 * channel, off >> 8)

def main():
    print("========================================")
    print("   SERVO ANGLE CALIBRATION TOOL         ")
    print("========================================")
    
    try:
        pwm = SimplePCA9685()
    except Exception as e:
        print(f"Error connecting to PCA9685: {e}")
        return

    servo_channel = 0
    
    # These are the boundaries we currently use in the main script
    servo_min = 102
    servo_max = 512

    print(f"\nCurrently configured boundaries:")
    print(f"0 Degrees   -> Pulse {servo_min}")
    print(f"180 Degrees -> Pulse {servo_max}\n")

    while True:
        try:
            user_input = input("Enter angle (0 to 180) or 'q' to quit: ")
            
            if user_input.lower() == 'q':
                break
                
            angle = float(user_input)
            
            if angle < 0 or angle > 180:
                print("Please enter a valid angle between 0 and 180!")
                continue
                
            # Convert angle to pulse width
            pulse = int((angle / 180.0) * (servo_max - servo_min) + servo_min)
            print(f"--> Moving servo to {angle}° (Sending Pulse Width: {pulse})")
            
            pwm.set_pwm(servo_channel, 0, pulse)
            
        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            break

    print("\nCalibration tool exited.")

if __name__ == "__main__":
    main()
