"""Unit tests for catguard.photos (TDD RED for Phase 2, T005)."""
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from catguard.photos import Photo, build_photo_filepath, encode_photo
import numpy as np

class TestPhotoDataclass:
    def test_photo_instantiation(self):
        ts = datetime(2026, 3, 5, 12, 34, 56)
        photo = Photo(timestamp=ts, bytes=b"abc", source="clean-capture")
        assert photo.timestamp == ts
        assert photo.bytes == b"abc"
        assert photo.source == "clean-capture"

class TestBuildPhotoFilepath:
    def test_returns_date_subfolder_and_time_filename(self, tmp_path):
        ts = datetime(2026, 3, 5, 12, 34, 56)
        root = tmp_path
        path = build_photo_filepath(root, ts, "jpg")
        assert path.parent.name == "2026-03-05"
        assert path.name.startswith("12-34-56")
        assert path.suffix == ".jpg"

    def test_appends_collision_suffix(self, tmp_path):
        ts = datetime(2026, 3, 5, 12, 34, 56)
        root = tmp_path
        # Simulate existing file
        (root / "2026-03-05").mkdir()
        (root / "2026-03-05" / "12-34-56.jpg").write_bytes(b"foo")
        path = build_photo_filepath(root, ts, "jpg")
        assert "-1" in path.stem

class TestEncodePhoto:
    def test_encode_photo_returns_jpeg_bytes(self, monkeypatch):
        # Mock cv2.imencode to return proper JPEG bytes with SOI marker
        mock_buf = MagicMock()
        mock_buf.tobytes.return_value = b"\xff\xd8" + b"\x00" * 100  # JPEG SOI + data
        monkeypatch.setattr("catguard.photos.cv2.imencode", lambda *args, **kw: (True, mock_buf))
        
        frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
        out = encode_photo(frame, 95)
        assert isinstance(out, bytes)
        assert out[:2] == b"\xff\xd8"  # JPEG SOI marker

    def test_encode_photo_invalid_quality_raises(self):
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 128
        with pytest.raises(ValueError):
            encode_photo(frame, 150)
