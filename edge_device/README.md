# Emotion-Aware Smart Street Lighting System - Edge Device

This is the edge device codebase for a Raspberry Pi 4-based smart street lighting system. 

## Features
- **DNN Person Tracking**: Utilizes OpenCV DNN MobileNet-SSD to detect people, coupled with mathematical centroid tracking. Estimates px/s speed and flags stationary loitering.
- **Graceful ML Failover**: If TensorFlow or DNN models cannot be located, the code gracefully falls back to basic hardware difference tracking without crashing.
- **Explainable Suspicious Activity**: Triggers targeted alerts using conservative labels (`Rapid_Movement_Night`, `Prolonged_Loitering`, `Crowd_Gathering`) rather than ambiguous predictions.
- **Picamera2 Support**: Fully avoids standard V4L2 timeout issues by relying cleanly on `libcamera`.

## Project Structure
- `config.py`: Hardcoded GPIOs and URLs. **Modify this** if your pinout changes.
- `edge_main.py`: The autonomous central loop capturing frames, deciding actions, and triggering hardware.
- `components_test.py`: The script you should run **first** to verify every piece of hardware works.
- `hardware_controller.py`: Clean wrapper around BCM pins and I2C commands.
- `camera_manager.py`: Picamera2 wrapper.
- `emotion_model.py`: Robust TFLite and Keras wrapper resolving dependency crashes.
- `decision_engine.py`: Rules dictating when the light turns on, servo angle, and event generation.
- `snapshots/`: Where local images are temporarily stored before upload.
- `models/`: **You must place your `emotion.tflite` or `emotion_detection_model.h5` in this directory.**

## Troubleshooting Known Issues
1. **TensorFlow/TFLite Not Installing**: This codebase is designed defensively. It will log that the model is missing and return a `Neutral` classification for faces, allowing the rest of the security system (PIR, LDR, Movement, Camera tracking) to function perfectly.
2. **Camera V4L2 Timeout**: Run the codebase inside an environment that has `picamera2` installed, not an older OpenCV `cv2.VideoCapture(0)` which is deprecated on Pi 4 with Bullseye/Bookworm+.
3. **Servo PWM Failing**: Check your `config.py` for the correct `PCA9685_ADDRESS` (defaults to `0x40`). The script tries `smbus2` first, then falls back to `smbus`.

## First Steps
1. Insert your model into the `models/` directory:
   ```bash
   cp ~/Downloads/emotion.tflite edge_device/models/
   cp ~/Downloads/MobileNetSSD_deploy.prototxt edge_device/models/
   cp ~/Downloads/MobileNetSSD_deploy.caffemodel edge_device/models/
   ```
2. Verify all hardware works (including the MobileNetSSD detector):
   ```bash
   python components_test.py
   ```
3. Run the main system:
   ```bash
   bash run.sh
   ```
