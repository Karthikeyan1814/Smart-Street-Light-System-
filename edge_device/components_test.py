"""
components_test.py
Standalone hardware test suite to verify Raspberry Pi pins, I2C, Camera, and GPIOs.
"""
import time
import sys
import os
import logging

# Ensure logging hits stdout for tests
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Add local path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from hardware_controller import HardwareController
from camera_manager import CameraManager

def print_header(title):
    print(f"\n{'='*50}")
    print(f"[{title}]")
    print(f"{'='*50}")

def run_tests():
    print_header("Initializing Hardware")
    try:
        hw = HardwareController()
        cam = CameraManager()
    except Exception as e:
        print(f"Failed to initialize controllers: {e}")
        return
    
    # 1. Camera Test
    print_header("1. Camera Test")
    cam.start()
    time.sleep(2) # Warmup
    frame = cam.get_frame()
    if frame is not None:
        print(f"PASS: Captured frame shape: {frame.shape}")
    else:
        print("FAIL: Camera could not capture frame (or not connected). Check logging warnings.")
    cam.stop()
    
    # 2. Sensor Test (PIR and LDR)
    print_header("2. Sensor Test (PIR & LDR)")
    print("Reading sensors for 5 seconds. Wave your hand over PIR and cover LDR!")
    for _ in range(5):
        pir_state = hw.is_motion_detected()
        ldr_state = hw.is_dark()
        print(f"PIR Motion: {pir_state}  |  LDR Dark: {ldr_state}")
        time.sleep(1)
        
    # 3. MOSFET PWM Test
    print_header("3. MOSFET PWM Brightness Test")
    print("Ramping brightness 0% -> 100% -> 0%")
    for p in range(0, 101, 20):
        hw.set_light_brightness(p)
        print(f"Brightness: {p}%")
        time.sleep(0.5)
    for p in range(100, -1, -20):
        hw.set_light_brightness(p)
        print(f"Brightness: {p}%")
        time.sleep(0.5)
    hw.set_light_brightness(0)
    print("PASS: MOSFET Ramp finished.")
    
    # 4. Servo Test
    print_header("4. Servo Sweep Test (PCA9685)")
    print("Sweeping 0 -> 90 -> 180 -> 90")
    for angle in [0, 45, 90, 135, 180, 90]:
        hw.set_servo_angle(angle)
        print(f"Servo Angle: {angle}")
        time.sleep(1.0)
    print("PASS: Servo Sweep finished.")
    
    # 5. Relay Test
    print_header("5. Relay Test (CH1 & CH2)")
    print("Toggling Relay CH1 ON/OFF")
    hw.toggle_relay(1, True)
    time.sleep(1)
    hw.toggle_relay(1, False)
    
    print("Toggling Relay CH2 ON/OFF")
    hw.toggle_relay(2, True)
    time.sleep(1)
    hw.toggle_relay(2, False)
    
    print("PASS: Relay toggle finished.")
    
    # 6. AI Subsystem Tests
    print_header("6. AI Subsystem Test")
    try:
        from person_detector import PersonDetector
        from person_tracker import CentroidTracker
        
        print("Initializing PersonDetector (MobileNet SSD)...")
        detector = PersonDetector()
        print(f"Detector Active/Loaded: {detector.available}")
        
        print("Initializing CentroidTracker...")
        tracker = CentroidTracker()
        
        if detector.available and cam.picam2:
            print("Grabbing frame for AI test...")
            cam.start()
            time.sleep(2)
            frame = cam.get_frame()
            if frame is not None:
                dets = detector.detect(frame)
                objects = tracker.update(dets)
                print(f"PASS: AI inference ran. Found {len(dets)} distinct persons.")
            else:
                print("FAIL: No frame for AI inference.")
            cam.stop()
        else:
            print("WARN: Detector not fully active (missing models) or Camera unavailable. Skipping inference.")
            
    except Exception as e:
        print(f"FAIL: AI tests crashed: {e}")
    
    print_header("Cleanup")
    hw.cleanup()
    print("All tests completed.")

if __name__ == "__main__":
    run_tests()
