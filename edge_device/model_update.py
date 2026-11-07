"""
model_update.py
Placeholder for OTA Model update logic.
"""
import logging
import requests
import os

logger = logging.getLogger(__name__)

def fetch_latest_model_versions(hub_url):
    """
    Queries hub for latest model hashes/versions.
    """
    try:
        res = requests.get(f"{hub_url}/models/latest", timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        logger.error(f"Failed to check model updates: {e}")
    return None

def download_model(url, dest_path):
    """
    Downloads model to dest_path safely.
    """
    try:
        logger.info(f"Downloading model from {url} to {dest_path}")
        res = requests.get(url, stream=True, timeout=30)
        res.raise_for_status()
        
        temp_path = dest_path + ".tmp"
        with open(temp_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)
                
        os.replace(temp_path, dest_path)
        logger.info("Model update successful.")
        return True
    except Exception as e:
        logger.error(f"Failed model download: {e}")
        return False
