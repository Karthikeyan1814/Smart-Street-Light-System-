"""
download_models.py

A quick helper script to download pre-trained Emotion (ONNX) and 
Person Detection (MobileNetSSD Caffe) models directly into the `models/` directory.

Run this on your Raspberry Pi: `python download_models.py`
"""
import os
import urllib.request
import logging

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")

# We use reliable, open-source model weights hosted explicitly for OpenCV DNN
MODELS = {
    # Lightweight FER2013 ONNX Model for Emotion Detection
    "emotion.onnx": "https://github.com/onnx/models/raw/main/validated/vision/body_analysis/emotion_ferplus/model/emotion-ferplus-8.onnx",
    
    # MobileNet-SSD for Person Detection
    "MobileNetSSD_deploy.prototxt": "https://raw.githubusercontent.com/djmv/MobilNet_SSD_opencv/master/MobileNetSSD_deploy.prototxt",
    "MobileNetSSD_deploy.caffemodel": "https://github.com/djmv/MobilNet_SSD_opencv/raw/master/MobileNetSSD_deploy.caffemodel"
}

def download_file(filename, url):
    filepath = os.path.join(MODEL_DIR, filename)
    if os.path.exists(filepath):
        logger.info(f"'{filename}' already exists. Skipping download.")
        return

    logger.info(f"Downloading '{filename}'...")
    try:
        urllib.request.urlretrieve(url, filepath)
        logger.info(f"[+] Successfully downloaded {filename}")
    except Exception as e:
        logger.error(f"[-] Failed to download {filename}: {e}")

if __name__ == "__main__":
    os.makedirs(MODEL_DIR, exist_ok=True)
    logger.info(f"Downloading pre-trained models into {MODEL_DIR}...")
    
    for filename, url in MODELS.items():
        download_file(filename, url)
        
    logger.info("Done! You can now run the edge device.")
