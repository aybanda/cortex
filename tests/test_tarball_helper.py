"""
Unit tests for tarball_helper.py
"""

import json
import os
import shutil
import tempfile

import pytest

from cortex.tarball_helper import MANUAL_TRACK_FILE, TarballHelper


def test_analyze_cmake(tmp_path):
    cmake = tmp_path / "CMakeLists.txt"
    cmake.write_text("""
    find_package(OpenSSL)
    find_package(ZLIB)
    """)
    helper = TarballHelper()
    deps = helper.analyze(str(tmp_path))
    assert set(deps) == {"OpenSSL", "ZLIB"}


def test_analyze_meson(tmp_path):
    meson = tmp_path / "meson.build"
    meson.write_text("dependency('libcurl')\ndependency('zlib')")
    helper = TarballHelper()
    deps = helper.analyze(str(tmp_path))
    assert set(deps) == {"libcurl", "zlib"}


def test_suggest_apt_packages():
    helper = TarballHelper()
    mapping = helper.suggest_apt_packages(["OpenSSL", "zlib"])
    assert mapping["OpenSSL"] == "libopenssl-dev"
    assert mapping["zlib"] == "libzlib-dev"


def test_track_and_cleanup(tmp_path, monkeypatch):
    # Patch MANUAL_TRACK_FILE to a temp location
    test_file = tmp_path / "manual_builds.json"
    monkeypatch.setattr("cortex.tarball_helper.MANUAL_TRACK_FILE", test_file)
    helper = TarballHelper()
    helper.track("libfoo-dev")
    assert "libfoo-dev" in helper.tracked_packages
    # Simulate cleanup (mock subprocess)
    monkeypatch.setattr("subprocess.run", lambda *a, **k: None)
    helper.cleanup()
    assert helper.tracked_packages == []
    with open(test_file) as f:
        data = json.load(f)
        assert data["packages"] == []
