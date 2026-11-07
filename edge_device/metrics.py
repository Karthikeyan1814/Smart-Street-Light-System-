"""
metrics.py
Tracks system resource usage (CPU, RAM, Temp).
"""
import psutil

def get_system_metrics():
    """
    Returns dict of current system metrics.
    """
    metrics = {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_percent": psutil.virtual_memory().percent,
        "temperature_c": 0.0
    }
    
    # Try getting Pi temperature
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = float(f.read().strip()) / 1000.0
            metrics["temperature_c"] = round(temp, 1)
    except:
        pass
        
    return metrics
