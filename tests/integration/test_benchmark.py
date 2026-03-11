"""T041: Performance benchmark for DetectionLoop.

Verifies:
- p95 frame processing latency ≤ 200ms (FR6)
- Peak RSS memory ≤ 100MB (constitution Tech Constraints)

Run with:
    pytest tests/integration/test_benchmark.py -v -s

These tests use real YOLO model and synthetic frames; skip if onnxruntime missing.
"""
from __future__ import annotations

import gc
import time
import tracemalloc
from statistics import quantiles

import numpy as np
import pytest

pytest.importorskip("onnxruntime", reason="onnxruntime not installed — skipping benchmark")

from catguard.config import Settings
from catguard.detection import (
    CAT_CLASS_ID,
    DetectionLoop,
    _INPUT_SIZE,
    _postprocess,
    _preprocess_frame,
)


def _blank_frame(h: int = 480, w: int = 640) -> "np.ndarray":
    return np.zeros((h, w, 3), dtype=np.uint8)


def _run_inference(loop: DetectionLoop, frame: "np.ndarray") -> list:
    blob = _preprocess_frame(frame, _INPUT_SIZE)
    raw_out = loop._model.run(None, {loop._model_input_name: blob})[0]
    return _postprocess(raw_out, loop._settings.confidence_threshold, CAT_CLASS_ID, frame.shape)


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

        # Warm up
        _run_inference(loop, frame)

        N = 20
        latencies = []
        for _ in range(N):
            t0 = time.perf_counter()
            _run_inference(loop, frame)
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
        _run_inference(loop, frame)

        _current, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak_bytes / (1024 * 1024)
        print(f"\n  Peak traced memory: {peak_mb:.1f} MB  (limit: 100 MB)")
        assert peak_mb <= 100.0, f"Peak memory {peak_mb:.1f} MB exceeds 100 MB gate"
