"""Stamp release metadata in the build checkout before Godot exports it."""

import argparse
import re
from pathlib import Path


def stamp(tag: str, project: Path) -> None:
    match = re.fullmatch(
        r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
        r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
        r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?", tag
    )
    if not match or any(int(part) > 65535 for part in match.group(1, 2, 3)):
        raise ValueError("Release tags must use vMAJOR.MINOR.PATCH with optional prerelease/build metadata; numeric components must fit Windows version fields.")
    version = tag.removeprefix("v")
    numeric = ".".join(match.group(1, 2, 3))
    presets = project / "export_presets.cfg"
    text = presets.read_text(encoding="utf-8")
    for key, value in {
        "application/file_version": numeric + ".0",
        "application/product_version": numeric + ".0",
        "application/short_version": numeric,
        "application/version": numeric,
    }.items():
        text, count = re.subn(r'(?m)^' + re.escape(key) + r'="[^"\n]*"$', f'{key}="{value}"', text)
        if count != 1:
            raise ValueError(f"Expected one export setting: {key}")
    settings = project / "project.godot"
    config = settings.read_text(encoding="utf-8")
    config, count = re.subn(r'(?m)^config/version="[^"\n]*"\n?', '', config)
    config, sections = re.subn(r'(?m)^\[application\]$', f'[application]\nconfig/version="{version}"', config)
    if sections != 1 or count > 1:
        raise ValueError("Expected one application section and at most one project version.")
    presets.write_text(text, encoding="utf-8", newline="\n")
    settings.write_text(config, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    args = parser.parse_args()
    stamp(args.tag, Path(__file__).resolve().parents[1] / "game")
