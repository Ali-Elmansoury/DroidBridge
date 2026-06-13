"""Tests for droidbridge.gui.preview_ops (Phase 6.2) — plain functions, no Qt."""

import os
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from droidbridge.gui import preview_ops
from droidbridge.modules.files import FileEntry


def make_entry(name="photo.jpg", size=1000, is_dir=False):
    return FileEntry(
        name=name,
        path=f"/sdcard/DCIM/{name}",
        is_dir=is_dir,
        is_symlink=False,
        size=size,
        mtime=datetime(2023, 8, 1, 10, 0),
    )


class TestIsPreviewable:
    def test_jpg_is_previewable(self):
        assert preview_ops.is_previewable(make_entry("photo.jpg")) is True

    def test_uppercase_extension_is_previewable(self):
        assert preview_ops.is_previewable(make_entry("PHOTO.JPG")) is True

    def test_directory_is_not_previewable(self):
        assert preview_ops.is_previewable(make_entry("Camera", is_dir=True)) is False

    def test_unsupported_extension_is_not_previewable(self):
        assert preview_ops.is_previewable(make_entry("video.mp4")) is False


class TestCachePath:
    def test_same_entry_returns_same_path(self, tmp_path):
        entry = make_entry()

        path1 = preview_ops.cache_path(str(tmp_path), entry)
        path2 = preview_ops.cache_path(str(tmp_path), entry)

        assert path1 == path2

    def test_different_size_returns_different_path(self, tmp_path):
        entry1 = make_entry(size=1000)
        entry2 = make_entry(size=2000)

        assert preview_ops.cache_path(str(tmp_path), entry1) != preview_ops.cache_path(str(tmp_path), entry2)

    def test_path_keeps_extension(self, tmp_path):
        entry = make_entry("photo.jpg")

        assert preview_ops.cache_path(str(tmp_path), entry).endswith(".jpg")


class TestFetchPreview:
    def test_pulls_and_returns_cache_path_when_not_cached(self, tmp_path):
        entry = make_entry()
        client = MagicMock()

        def fake_pull(serial, remote, local):
            with open(local, "wb") as f:
                f.write(b"fake-image-bytes")

        client.pull.side_effect = fake_pull

        result = preview_ops.fetch_preview(client, "SERIAL", entry, cache_dir=str(tmp_path))

        assert os.path.exists(result)
        client.pull.assert_called_once_with("SERIAL", entry.path, result)

    def test_does_not_repull_when_cached(self, tmp_path):
        entry = make_entry()
        client = MagicMock()

        def fake_pull(serial, remote, local):
            with open(local, "wb") as f:
                f.write(b"fake-image-bytes")

        client.pull.side_effect = fake_pull

        first = preview_ops.fetch_preview(client, "SERIAL", entry, cache_dir=str(tmp_path))
        second = preview_ops.fetch_preview(client, "SERIAL", entry, cache_dir=str(tmp_path))

        assert first == second
        client.pull.assert_called_once()

    def test_raises_when_too_large(self, tmp_path):
        entry = make_entry(size=preview_ops.MAX_PREVIEW_SIZE + 1)
        client = MagicMock()

        with pytest.raises(preview_ops.PreviewTooLargeError):
            preview_ops.fetch_preview(client, "SERIAL", entry, cache_dir=str(tmp_path))

        client.pull.assert_not_called()
