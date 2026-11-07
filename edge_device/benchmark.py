import statistics
import time

import numpy as np

from emotion_model import EmotionModel
from metrics import collect_metrics


def main() -> None:
  model = EmotionModel()
  num_runs = 100
  inference_times = []
  cpu_samples = []

  for _ in range(num_runs):
      # Use a synthetic frame (black image); on real hardware this can
      # be replaced with actual camera frames.
      frame = np.zeros((480, 640, 3), dtype=np.uint8)
      _, _, inference_ms = model.predict(frame)
      sample = collect_metrics(inference_ms)
      inference_times.append(inference_ms)
      cpu_samples.append(sample["cpu_percent"])

  avg_time = statistics.mean(inference_times)
  max_cpu = max(cpu_samples) if cpu_samples else 0.0
  avg_cpu = statistics.mean(cpu_samples) if cpu_samples else 0.0

  print("Benchmark results (100 synthetic frames):")
  print(f"  avg_inference_time_ms = {avg_time:.2f}")
  print(f"  max_cpu_usage_percent = {max_cpu:.1f}")
  print(f"  avg_cpu_usage_percent = {avg_cpu:.1f}")


if __name__ == "__main__":
  main()

