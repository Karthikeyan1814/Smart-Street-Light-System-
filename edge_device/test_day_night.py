import RPi.GPIO as GPIO
import time

# Pin Definitions
LDR_PIN = 22
PWM_MOSFET_PIN = 17
RELAY_CH1 = 20

# Active logic for the LDR. (1 = Dark according to user's earlier tests)
NIGHT_LDR_VALUE = 1

def main():
    print("--- Day/Night Physical Hardware Test ---")
    
    # Configure GPIO
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    
    # Setup LDR
    GPIO.setup(LDR_PIN, GPIO.IN)
    
    # Setup MOSFET
    GPIO.setup(PWM_MOSFET_PIN, GPIO.OUT)
    GPIO.output(PWM_MOSFET_PIN, GPIO.LOW)
    pwm = GPIO.PWM(PWM_MOSFET_PIN, 100) # 100Hz
    pwm.start(0)
    
    # Setup Relay 1 (Floodlight Power)
    GPIO.setup(RELAY_CH1, GPIO.OUT, initial=GPIO.LOW) # Active HIGH means LOW = OFF
    
    try:
        print("Starting monitoring... Press Ctrl+C to quit.")
        last_state = None
        
        while True:
            # Read Sensor
            ldr_state = GPIO.input(LDR_PIN)
            is_night = (ldr_state == NIGHT_LDR_VALUE)
            
            # If state changed, print and execute!
            if is_night != last_state:
                if is_night:
                    print(f"--> NIGHT DETECTED (LDR: {ldr_state}). Floodlight Powering ON!")
                    pwm.ChangeDutyCycle(100)          # Max Brightness MOSFET
                    GPIO.output(RELAY_CH1, GPIO.HIGH)   # Turn on Relay (Active HIGH)
                else:
                    print(f"--> DAY DETECTED (LDR: {ldr_state}). Floodlight Shutting DOWN.")
                    pwm.ChangeDutyCycle(0)            # Off MOSFET
                    GPIO.output(RELAY_CH1, GPIO.LOW)  # Turn off Relay (Active HIGH)
                
                last_state = is_night
                
            time.sleep(0.1) # Rapidly read sensor
            
    except KeyboardInterrupt:
        print("\nTest stopped by user.")
    finally:
        print("Cleaning up GPIO...")
        pwm.stop()
        GPIO.output(RELAY_CH1, GPIO.LOW) # Turn off Relay securely
        GPIO.cleanup()

if __name__ == "__main__":
    main()
