"""
model_validation.py
Validates the structural integrity or hash of a downloaded model before using it.
"""
import hashlib
import logging

logger = logging.getLogger(__name__)

def verify_file_hash(filepath, expected_hash, algo="sha256"):
    """
    Verifies the file at filepath against expected_hash.
    """
    try:
        h = hashlib.new(algo)
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
                
        actual_hash = h.hexdigest()
        if actual_hash == expected_hash:
            return True
        else:
            logger.warning(f"Hash mismatch for {filepath}. Expected {expected_hash}, got {actual_hash}")
            return False
            
    except Exception as e:
        logger.error(f"Hash verification failed: {e}")
        return False
