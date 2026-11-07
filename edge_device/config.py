"""
config.py
Configuration variables for the Smart Street Lighting Edge Device.
"""
import os

# Tower Info
TOWER_ID = os.getenv("TOWER_ID", "TOWER-01")
LOCATION = os.getenv("LOCATION", "Smart Campus - Street Light Zone")

# Operation Override (Controlled by Dashboard)
OVERRIDE_MODE = "AUTO"  # "AUTO", "DAY", "NIGHT"
OVERRIDE_MOSFET = "AUTO" # "AUTO", "FULL"

# Hardware Pins (BCM)
PIR_PIN = 27
LDR_PIN = 22
PWM_MOSFET_PIN = 17
PCA9685_ADDRESS = 0x40
SERVO_CHANNEL = 0
RELAY_CH1 = 20 # Main flood light relay (Active LOW)
RELAY_CH2 = 21 # IR LED for camera (Active LOW)

# Servo Angles
SERVO_MIN_ANGLE = 40
SERVO_MAX_ANGLE = 180
SERVO_DEFAULT_ANGLE = 110 # Forward / ground direction
SERVO_STEP = 5

# Light Control
PWM_FREQ = 100
DAY_BRIGHTNESS = 0
NIGHT_BRIGHTNESS_IDLE = 50   # 50% initial idle brightness (per user request)
NIGHT_BRIGHTNESS_ACTIVE = 100 # 100% when tracking detected targets

# Thresholds
MOTION_COOLDOWN_SEC = 5.0
PERSON_CONFIDENCE_THRESHOLD = 0.55 # Ignore weak DNN detections (e.g. hands/shadows)
LDR_DARK_VALUE = 1  # Active-HIGH logic: 1 means it is dark, 0 means daylight
SPEED_SLOW_THRESHOLD = 15.0     # px/s (Increased to prevent accidental micro-movement loitering labels)
SPEED_NORMAL_THRESHOLD = 20.0  # px/s
SPEED_FAST_THRESHOLD = 50.0    # px/s
LOITERING_THRESHOLD_SEC = 30.0 # seconds before tagging as loitering

# Model Paths
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
TFLITE_MODEL_PATH = os.path.join(MODEL_DIR, "emotion.tflite")
KERAS_MODEL_PATH = os.path.join(MODEL_DIR, "emotion_detection_model.h5")
DNN_PROTOTXT = os.path.join(MODEL_DIR, "MobileNetSSD_deploy.prototxt")
DNN_MODEL = os.path.join(MODEL_DIR, "MobileNetSSD_deploy.caffemodel")

# Camera (Enforce 16:9 ratio to unlock the full 120-degree FOV without center-cropping the NOIR sensor)
IMAGE_WIDTH = 1280
IMAGE_HEIGHT = 720
FRAMERATE = 15

# API Endpoints (Hub)
HUB_URL_BASE = os.getenv("HUB_URL", "http://[IP_ADDRESS]/api")
EVENTS_ENDPOINT = f"{HUB_URL_BASE}/alert"
HEARTBEAT_ENDPOINT = f"{HUB_URL_BASE}/heartbeat"
API_KEY = os.getenv("HUB_API_KEY", "hello-from-pi-lets-make-it-work")

# Directories
SNAPSHOTS_DIR = os.path.join(os.path.dirname(__file__), "snapshots")
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)
