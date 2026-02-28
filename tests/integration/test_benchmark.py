"""T041: Performance benchmark for DetectionLoop.

Verifies:
- p95 frame processing latency ≤ 200ms (FR6)
- Peak RSS memory ≤ 100MB (constitution Tech Constraints)

Run with:
    pytest tests/integration/test_benchmark.py -v -s

These tests use real YOLO model and synthetic frames; skip if ultralytics missing.
"""
from __future__ import annotations

import gc
import time
import tracemalloc
from statistics import quantiles

import numpy as np
import pytest

pytest.importorskip("ultralytics", reason="ultralytics not installed — skipping benchmark")

from catguard.config import Settings
from catguard.detection import CAT_CLASS_ID, DetectionLoop


def _blank_frame(h: int = 480, w: int = 640) -> "np.ndarray":
    return np.zeros((h, w, 3), dtype=np.uint8)


@pytest.mark.integration
class TestBenchmark:
    """Performance gates for DetectionLoop (FR6 + constitution)."""

    def _load_loop(self) -> DetectionLoop:
        loop = DetectionLoop(Settings(), lambda e: None)
        loop._load_model()
        return loop

    def test_p95_latency_under_200ms(self):
        """p95 single-frame YOLO inference latency must be ≤ 200 ms."""
        loop = self._load_loop()
        frame = _blank_frame()
        settings = loop._settings

        # Warm up
        loop._model.predict(frame, conf=settings.confidence_threshold, classes=[CAT_CLASS_ID], device="cpu", verbose=False)

        N = 20
        latencies = []
        for _ in range(N):
            t0 = time.perf_counter()
            loop._model.predict(frame, conf=settings.confidence_threshold, classes=[CAT_CLASS_ID], device="cpu", verbose=False)
            latencies.append((time.perf_counter() - t0) * 1000)  # ms

        latencies.sort()
        p95 = quantiles(latencies, n=20)[18]  # 95th percentile (index 18 of 20 quantiles)
        print(f"\n  YOLO inference p95 latency: {p95:.1f} ms  (limit: 200 ms)")
        assert p95 <= 200.0, f"p95 latency {p95:.1f} ms exceeds 200 ms gate"

    def test_peak_memory_under_100mb(self):
        """Peak additional RSS from loading model + running inference must be ≤ 100 MB."""
        gc.collect()
        tracemalloc.start()

        loop = self._load_loop()
        frame = _blank_frame()
        loop._model.predict(frame, conf=0.40, classes=[CAT_CLASS_ID], device="cpu", verbose=False)

        _current, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak_bytes / (1024 * 1024)
        print(f"\n  Peak traced memory: {peak_mb:.1f} MB  (limit: 100 MB)")
        assert peak_mb <= 100.0, f"Peak memory {peak_mb:.1f} MB exceeds 100 MB gate"
