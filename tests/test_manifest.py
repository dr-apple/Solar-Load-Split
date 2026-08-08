"""Manifest compatibility tests."""

import json
from pathlib import Path


def test_manifest_metadata() -> None:
    """The custom integration declares current Home Assistant metadata."""
    manifest = json.loads(Path("custom_components/pv_device_split/manifest.json").read_text())

    assert manifest["integration_type"] == "helper"
    assert manifest["iot_class"] == "calculated"
    assert manifest["codeowners"] == ["@dr-apple"]
    assert manifest["documentation"] == "https://github.com/dr-apple/Solar-Load-Split"
